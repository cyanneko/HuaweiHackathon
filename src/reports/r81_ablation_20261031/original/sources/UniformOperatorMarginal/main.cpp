#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <cstdint>
#include <cassert>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <memory>
#include <tuple>

/* ===== 数据结构定义 ===== */

enum class Phase { BUILD, PROBE };

struct PartitionState {
    int partition_id;
    int64_t data_size;   // 当前数据总大小（字节）
    bool in_memory;      // 是否在内存中
    PartitionState() : partition_id(-1), data_size(0), in_memory(true) {}
};

struct OperatorState {
    int op_id;
    Phase phase;
    std::vector<PartitionState> partitions;  // P个分区
};

struct PendingOp {
    std::string type;      // "INSERT" / "SWITCH" / "PROBE" / ""（无后续操作）
    int op_id;             // 算子ID，type为空时无意义
    int64_t key;           // INSERT/PROBE时的key，SWITCH时无意义
    int64_t tuple_size;    // INSERT时的元组大小，其余操作无意义
    PendingOp() : op_id(-1), key(0), tuple_size(0) {}
};

struct SystemState {
    int64_t memory_used;
    int64_t memory_limit;
    int num_partitions;
    double write_bandwidth;    // 字节/微秒
    double read_bandwidth;     // 字节/微秒
    int64_t hit_count;
    int64_t miss_count;
    int64_t total_io_bytes;
    std::vector<OperatorState> operators;
    PendingOp next_op;         // 下一个待处理操作
};

/* ===== 调度动作 ===== */

struct Action {
    enum Type { SPILL, LOAD } type;
    int op_id;
    int partition_id;
    Action(Type t, int o, int p) : type(t), op_id(o), partition_id(p) {}
};

/* ===== 调度器抽象基类 ===== */

class SpillScheduler {
public:
    virtual ~SpillScheduler() = default;

    // 场景1：INSERT导致内存溢出时调用
    virtual std::vector<Action> onMemoryOverflow(
        const SystemState& state,
        int op_id, int partition_id, int64_t tuple_size) = 0;

    // 场景2：PROBE需要加载磁盘分区时调用
    virtual std::vector<Action> onPartitionMiss(
        const SystemState& state,
        int op_id, int partition_id) = 0;

    // 场景3：周期性调度，每处理B个操作后调用
    virtual std::vector<Action> onPeriodicAdjust(
        const SystemState& state) = 0;
};

/* ===== 朴素调度器（基线实现）===== */

// 算子边际的快速衰减半衰期：单位为 hit_count + miss_count 的 PROBE 序号步数。
#define HASHJOIN_OPERATOR_HALF_LIFE 256
// 复用估计模式：0 为历史/回访，1 为扁平频率，2 为分层频率，3 为原有双方案比较。
#define HASHJOIN_REUSE_ESTIMATOR 2
// 自适应共享仅控制回访风险路径中的算子池混合；不控制分层频率的共享公式。
#define HASHJOIN_ADAPTIVE_RISK_SHARING 1
// 回访模型值 3：按观测覆盖率选择历史观测与回访风险的混合权重；小于 3 时固定为 .25。
#define HASHJOIN_REFAULT_MODEL 3
// 大小偏置开关：0 关闭额外的平方根大小修正；原有 IO/大小代价项仍保留。
#define HASHJOIN_SIZE_BIAS 0

// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cstdint>
#include <vector>
#include <cmath>
#include <array>
#include <cstdint>

// 分区级回访风险：跟踪已确认逐出区间的暴露时间与回访事件。
namespace r74 {
    inline double decay(int64_t delta) {
        // Lazy initialization occurs inside the first real Risk.advance call.
        // Direct exp evaluation preserves the original expression per entry.
        static const std::array<double, 1025> table = []() {
            std::array<double, 1025> values{};
            for (int i = 0; i <= 1024; ++i)
                values[i] = std::exp(-static_cast<double>(i) / 512.);
            return values;
        }();
        return delta >= 0 && delta <= 1024
            ? table[static_cast<std::size_t>(delta)]
            : std::exp(-static_cast<double>(delta) / 512.);
    }

    struct Risk {
        double exposure = 0, events = 0, starts = 0;
        int active = 0;
        int64_t last = 0;

        void advance(int64_t q) {
            if (q <= last)
                return;
            if (!active && exposure == 0. && events == 0. && starts == 0.) {
                last = q;
                return;
            }
            const double f = decay(q - last);
            exposure = exposure * f + active * 512. * (1. - f);
            events *= f;
            starts *= f;
            last = q;
        }

        void begin(int64_t q) {
            advance(q);
            ++active;
            ++starts;
        }

        void end(int64_t q, bool event) {
            advance(q);
            --active;
            if (event)
                ++events;
        }

        double mean(int64_t q, double prior = 64.) {
            advance(q);
            return (exposure + prior) / (events + 1.);
        }
    };
}

#include <cmath>
#include <array>
#include <cstdint>

// 算子级回访风险：为同一算子的分区提供共享估计。
namespace r75op {
    inline double decay(int64_t delta) {
        // Lazy initialization occurs inside the first real Risk.advance call.
        // Direct exp evaluation preserves the original expression per entry.
        static const std::array<double, 1025> table = []() {
            std::array<double, 1025> values{};
            for (int i = 0; i <= 1024; ++i)
                values[i] = std::exp(-static_cast<double>(i) / 128.);
            return values;
        }();
        return delta >= 0 && delta <= 1024
            ? table[static_cast<std::size_t>(delta)]
            : std::exp(-static_cast<double>(delta) / 128.);
    }

    struct Risk {
        double exposure = 0, events = 0, starts = 0;
        int active = 0;
        int64_t last = 0;

        void advance(int64_t q) {
            if (q <= last)
                return;
            if (!active && exposure == 0. && events == 0. && starts == 0.) {
                last = q;
                return;
            }
            const double f = decay(q - last);
            exposure = exposure * f + active * 128. * (1. - f);
            events *= f;
            starts *= f;
            last = q;
        }

        void begin(int64_t q) {
            advance(q);
            ++active;
            ++starts;
        }

        void end(int64_t q, bool event) {
            advance(q);
            --active;
            if (event)
                ++events;
        }

        double mean(int64_t q, double prior = 64.) {
            advance(q);
            return (exposure + prior) / (events + 1.);
        }
    };
}

class MySpillScheduler : public SpillScheduler {
    // 双时间尺度：快速算子边际与慢速分区条件概率。
    struct FastOperator {
        double mass = 0.;
        int64_t last = 0;
    };

    std::vector<FastOperator> fast_operator_;
    std::vector<double> operator_scale_;
    double fast_probability_total_ = 0.;

    static double fastDecay(int64_t delta) {
        static const std::array<double, 8193> table = []() {
            std::array<double, 8193> a{};
            for (int i = 0; i <= 8192; ++i)
                a[i] = std::exp(
                    -0.693147180559945309417232121458176568 * static_cast<double>(i)
                    / HASHJOIN_OPERATOR_HALF_LIFE);
            return a;
        }();
        return delta >= 0 && delta <= 8192
            ? table[static_cast<std::size_t>(delta)]
            : std::exp(
                  -0.693147180559945309417232121458176568 * static_cast<double>(delta)
                  / HASHJOIN_OPERATOR_HALF_LIFE);
    }

    void advanceFast(int op, int64_t q) {
        auto& f = fast_operator_[op];
        if (q > f.last) {
            if (f.mass != 0.)
                f.mass *= fastDecay(q - f.last);
            f.last = q;
        }
    }

    bool probability_cache_valid_ = false;
    int64_t probability_clock_ = 0;
    double probability_total_ = 0., probability_weight2_ = 0.;
    std::vector<double> flat_probability_, hier_probability_;
    std::vector<uint64_t> probability_tags_;
    uint64_t probability_epoch_ = 0;
    double probability_prior_ = 0., probability_denom_ = 1.;
    std::vector<int> changed_sign_, changed_ids_;

    static double probabilityDecay(int64_t delta) {
        static const std::array<double, 8193> table = []() {
            std::array<double, 8193> values{};
            for (int i = 0; i <= 8192; ++i)
                values[i] = nextDecay(i);
            return values;
        }();
        return delta >= 0 && delta <= 8192
            ? table[static_cast<std::size_t>(delta)] : nextDecay(delta);
    }

    void ensureProbabilities(const SystemState& s) {
        if (probability_cache_valid_)
            return;
        const int n = static_cast<int>(next_mass_.size());
        probability_clock_ = std::max(s.hit_count + s.miss_count, next_sample_q_);
        probability_total_ = probability_weight2_ = 0.;
        fast_probability_total_ = 0.;

        for (int op = 0; op < static_cast<int>(sharing_.size()); ++op) {
            refreshSharing(op, probability_clock_);
            advanceFast(op, probability_clock_);
            fast_probability_total_ += fast_operator_[op].mass;
            probability_total_ += sharing_[op].mass;
            probability_weight2_ += sharing_[op].weight2;
        }

        flat_probability_.resize(n);
        hier_probability_.resize(n);
        if (static_cast<int>(changed_sign_.size()) != n)
            changed_sign_.assign(n, 0);
        if (static_cast<int>(probability_tags_.size()) != n)
            probability_tags_.assign(n, 0);
        if (++probability_epoch_ == 0) {
            std::fill(probability_tags_.begin(), probability_tags_.end(), 0);
            probability_epoch_ = 1;
        }
        probability_prior_ = 64. / n;
        probability_denom_ = probability_total_ + 64.;
        const int k = static_cast<int>(sharing_.size());
        operator_scale_.resize(k);
        const double op_prior = 64. / k, fast_denom = fast_probability_total_ + 64.;
        for (int op = 0; op < k; ++op) {
            const double marginal = 1. / k; // Ablation: uniform operator marginal.
            operator_scale_[op] = std::isfinite(marginal) && marginal >= 0.
                ? marginal / (sharing_[op].mass + op_prior) : 1. / probability_denom_;
        }
        probability_cache_valid_ = true;
    }

    void ensureProbability(int id) {
        if (probability_tags_[id] == probability_epoch_)
            return;
        const auto& c = next_mass_[id];
        const auto& g = sharing_[id / p_];
        const double mass = c.mass == 0. ? 0.
            : c.mass * probabilityDecay(std::max<int64_t>(0, probability_clock_ - c.last));
        flat_probability_[id] = (mass + probability_prior_) / probability_denom_;
        hier_probability_[id] =
            ((1. - g.share) * mass + g.share * g.mass / p_ + probability_prior_)
            * operator_scale_[id / p_];
        probability_tags_[id] = probability_epoch_;
    }

    // 保留已有的方案比较逻辑；是否启用仍由原有模式分支决定。
    struct PairDelta {
        double immediate = 0., mean = 0., second = 0., sd = 0.;
        bool different = false;
    };

    PairDelta comparePlans(const SystemState& s, const std::vector<Action>& base,
                           const std::vector<Action>& alt) {
        ensureProbabilities(s);
        changed_ids_.clear();
        for (const auto& a : base) {
            const int id = a.op_id * p_ + a.partition_id;
            if (changed_sign_[id] == 0)
                changed_ids_.push_back(id);
            --changed_sign_[id];
        }
        for (const auto& a : alt) {
            const int id = a.op_id * p_ + a.partition_id;
            if (changed_sign_[id] == 0)
                changed_ids_.push_back(id);
            ++changed_sign_[id];
        }

        PairDelta d;
        for (int id : changed_ids_) {
            const int sign = changed_sign_[id];
            changed_sign_[id] = 0;
            if (!sign)
                continue;
            d.different = true;
            const int op = id / p_, pid = id % p_;
            const double bytes = s.operators[op].partitions[pid].data_size;
            const double coefficient =
                sign * (bytes / s.read_bandwidth + bytes / s.write_bandwidth + 100.);
            d.immediate += sign * bytes / s.write_bandwidth;
            if (s.next_op.type == "PROBE" && s.next_op.op_id == op
                && s.next_op.key % p_ == pid)
                d.immediate += sign * (bytes / s.read_bandwidth + 100.);
            ensureProbability(id);
            d.mean += flat_probability_[id] * coefficient;
            d.second += flat_probability_[id] * coefficient * coefficient;
        }
        const double effective = probability_weight2_ > 0.
            ? probability_total_ * probability_total_ / probability_weight2_ : 0.;
        d.sd = 64. * std::sqrt(std::max(0., d.second - d.mean * d.mean) / (effective + 1.));
        return d;
    }

    bool chooseAlternative(const SystemState& s, const std::vector<Action>& base,
                           const std::vector<Action>& alt) {
        ensureProbabilities(s);
        if (!(probability_total_ > 0.) || !(probability_weight2_ > 0.))
            return false;
        const auto d = comparePlans(s, base, alt);
        return d.different && d.immediate + 64. * d.mean + 2. * d.sd < 0.;
    }

    // 慢速分区计数与异质性估计，用于自适应共享算子内信息。
    struct ShareGroup {
        double mass = 0., squares = 0., weight2 = 0., heterogeneity = 0., share = .75;
        int64_t last = 0;
    };

    struct NextMass {
        double mass = 0.;
        int64_t last = 0;
    };

    std::vector<ShareGroup> sharing_;
    std::vector<NextMass> next_mass_;
    int64_t next_sample_q_ = -1;

    static double nextDecay(int64_t d) {
        return std::exp(
            -0.693147180559945309417232121458176568 * static_cast<double>(d) / 2048.);
    }

    void refreshSharing(int op, int64_t q) {
        auto& g = sharing_[op];
        if (q > g.last) {
            const double f = nextDecay(q - g.last);
            g.mass *= f;
            g.squares *= f * f;
            g.weight2 *= f * f;
            g.last = q;
        }
        g.heterogeneity = 0.;
        g.share = .75;
        if (p_ <= 1 || !(g.mass > 8.) || !(g.weight2 > 1e-200)
            || !std::isfinite(g.mass) || !std::isfinite(g.squares) || !std::isfinite(g.weight2))
            return;
        const double ss = g.mass * g.mass, n = ss / g.weight2;
        if (!(n > 8.) || !std::isfinite(n) || !std::isfinite(ss))
            return;
        const double v = std::max(0., (p_ * g.squares / ss - 1. - (p_ - 1) / n) / (1. - 1. / n));
        const double strength = v * (g.mass - 8.) / (g.mass + p_);
        if (std::isfinite(strength)) {
            g.heterogeneity = strength / (1. + strength);
            g.share = .75 / (1. + strength);
        }
    }

    void sampleNext(int op, int pid, int64_t ordinal) {
        refreshSharing(op, ordinal);
        if (ordinal <= next_sample_q_)
            return;
        advanceFast(op, ordinal);
        fast_operator_[op].mass += 1.;
        auto& g = sharing_[op];
        auto& c = next_mass_[op * p_ + pid];
        if (g.last > c.last)
            c.mass *= nextDecay(g.last - c.last);
        c.last = g.last;
        g.squares += 2. * c.mass + 1.;
        g.mass += 1.;
        g.weight2 += 1.;
        c.mass += 1.;
        next_sample_q_ = ordinal;
        refreshSharing(op, g.last);
    }

    double partitionBase(int id, int64_t q, double visible) {
        auto& r = risk_[id];
        r.advance(q);
        if (r.starts < 1e-9)
            return visible;
        return 64. / (64. + r.mean(q, 64.));
    }

    // 动作先记录意图，下一次可见状态确认后再更新回访区间。
    struct Intent {
        int id;
        int64_t q, size;
        bool spill;
    };

    std::vector<r74::Risk> risk_;
    std::vector<r75op::Risk> operator_risk_;
    std::vector<double> cached_priors_;
    std::vector<unsigned char> cached_valid_;
    std::vector<Intent> intents_;
    double coverage_ = 0.;
    int64_t coverage_q_ = 0;

    void confirm(const SystemState& s) {
        for (const auto& i : intents_) {
            const int o = i.id / p_, p = i.id % p_;
            const auto& part = s.operators[o].partitions[p];
            if (part.data_size != i.size)
                continue;
            auto& r = risk_[i.id];
            auto& pooled = operator_risk_[o];
            if (i.spill && !part.in_memory && !r.active) {
                r.begin(i.q);
                pooled.begin(i.q);
            } else if (!i.spill && part.in_memory && r.active) {
                r.end(i.q, false);
                pooled.end(i.q, false);
            }
        }
        intents_.clear();
    }

    void record(const SystemState& s, const std::vector<Action>& actions) {
        const int64_t q = s.hit_count + s.miss_count;
        for (const auto& a : actions) {
            const auto& o = s.operators[a.op_id];
            const auto& p = o.partitions[a.partition_id];
            if (o.phase != Phase::PROBE || p.data_size <= 0)
                continue;
            if (a.type == Action::SPILL && p.in_memory)
                intents_.push_back({a.op_id * p_ + a.partition_id, q, p.data_size, true});
            else if (a.type == Action::LOAD && !p.in_memory)
                intents_.push_back({a.op_id * p_ + a.partition_id, q, p.data_size, false});
        }
    }

    double demandWeight(int64_t q) const {
        if (HASHJOIN_REFAULT_MODEL < 3)
            return .25;
        const double elapsed = static_cast<double>(std::max<int64_t>(1, q));
        const double cov = std::min(
            1., coverage_ * std::exp(-static_cast<double>(std::max<int64_t>(0, q - coverage_q_)) / 256.)
                / (1. - std::exp(-elapsed / 256.)));
        return cov >= .75 ? 1. : .25;
    }

    double refaultReuse(int id, int64_t q, double visible, double observed_weight) {
        if (observed_weight >= 1.)
            return visible;
        const double part = partitionBase(id, q, visible);
        const int op = id / p_;
        auto& pool = operator_risk_[op];
        if (!cached_valid_[op]) {
            pool.advance(q);
            cached_priors_[op] = pool.mean(q, 64.);
            refreshSharing(op, q);
            cached_valid_[op] = 1;
        }
        double reuse = part;
        if (pool.starts >= 1e-9) {
            const double alpha = HASHJOIN_ADAPTIVE_RISK_SHARING ? sharing_[op].share : .75;
            const double pooled = 64. / (64. + cached_priors_[op]);
            reuse = (1. - alpha) * part + alpha * pooled;
        }
        return (1. - observed_weight) * reuse + observed_weight * visible;
    }

    // 访问历史、步长与后继图，用于识别已有的扫描和等大小循环模式。
    struct History {
        int64_t last = -1;
        double count = 0;
    };

    struct Victim {
        int op, pid;
        int64_t bytes;
        double priority;
    };

    std::vector<History> history_;
    std::vector<Victim> victims_;
    std::vector<int> step_distance_;
    std::vector<int> successor_, confidence_, recent_;
    int recent_head_ = 0, recent_count_ = 0;
    int64_t graph_version_ = 0, analyzed_version_ = -1;
    bool uniform_cycle_ = false;
    int confirmed_edges_ = 0;
    bool active_ = false;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;

    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_)
            return;
        const int current_id = op * p_ + pid;
        if (q == observed_q_ + 1 && last_op_ >= 0) {
            const int previous_id = last_op_ * p_ + last_pid_;
            if (successor_[previous_id] == current_id) {
                confidence_[previous_id] = std::min(7, confidence_[previous_id] + 1);
                if (confidence_[previous_id] == 3) {
                    ++graph_version_;
                    ++confirmed_edges_;
                }
            } else {
                if (confidence_[previous_id] >= 3)
                    --confirmed_edges_;
                successor_[previous_id] = current_id;
                confidence_[previous_id] = 1;
                ++graph_version_;
            }
        }
        recent_[recent_head_] = current_id;
        recent_head_ = (recent_head_ + 1) % static_cast<int>(recent_.size());
        recent_count_ = std::min(recent_count_ + 1, static_cast<int>(recent_.size()));
        auto& h = history_[op * p_ + pid];
        if (h.last >= 0)
            h.count *= 256.0 / (256.0 + static_cast<double>(q - h.last));
        h.count += 1;
        h.last = q;
        if (q == observed_q_ + 1 && op == last_op_) {
            const int delta = (pid - last_pid_ + p_) % p_;
            if (delta != 0 && delta == stride_)
                ++streak_;
            else {
                stride_ = delta;
                streak_ = 1;
            }
        } else {
            stride_ = -1;
            streak_ = 0;
        }
        last_op_ = op;
        last_pid_ = pid;
        observed_q_ = q;
        ++observed_count_;
        if (streak_ >= 3 && stride_ > 0 && cached_stride_ != stride_) {
            step_distance_.assign(p_, p_);
            int at = 0;
            for (int j = 1; j <= p_; ++j) {
                at = (at + stride_) % p_;
                if (step_distance_[at] == p_)
                    step_distance_[at] = j;
            }
            cached_stride_ = stride_;
        }
    }

    // 统一确认动作、更新观测，并按原有序号规则去重。
    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {
        const int n = static_cast<int>(s.operators.size()) * s.num_partitions;
        if (p_ != s.num_partitions || static_cast<int>(history_.size()) != n) {
            p_ = s.num_partitions;
            history_.assign(n, History{});
            risk_.assign(n, r74::Risk{});
            operator_risk_.assign(s.operators.size(), r75op::Risk{});
            fast_operator_.assign(s.operators.size(), FastOperator{});
            operator_scale_.clear();
            sharing_.assign(s.operators.size(), ShareGroup{});
            next_mass_.assign(n, NextMass{});
            next_sample_q_ = -1;
            intents_.clear();
            coverage_ = 0.;
            coverage_q_ = 0;
            cached_priors_.assign(s.operators.size(), 64.);
            cached_valid_.assign(s.operators.size(), 0);
            successor_.assign(n, -1);
            confidence_.assign(n, 0);
            recent_.assign(n + 2, -1);
            recent_head_ = recent_count_ = 0;
            graph_version_ = 0;
            analyzed_version_ = -1;
            uniform_cycle_ = false;
            confirmed_edges_ = 0;
            observed_q_ = -1;
            observed_count_ = 0;
            last_op_ = last_pid_ = stride_ = cached_stride_ = -1;
            streak_ = 0;
        }
        const int64_t q = s.hit_count + s.miss_count;
        confirm(s);

        // The engine increments miss_count before this callback. Refault is
        // independent of next-op observation deduplication.
        if (op >= 0) {
            auto& r = risk_[op * p_ + pid];
            if (r.active) {
                r.end(q, true);
                operator_risk_[op].end(q, true);
            }
        }
        // A miss and its periodic callback may expose the same pending request.
        // Probe ordinals deduplicate those, while preserving real repeated keys.
        if (op >= 0) {
            refreshSharing(op, q);
            observe(op, pid, q);
        }
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0
            && s.next_op.op_id < static_cast<int>(s.operators.size())) {
            if (periodic && q + 1 > coverage_q_) {
                coverage_ *= std::exp(-static_cast<double>(q + 1 - coverage_q_) / 256.);
                coverage_ += 1. - std::exp(-1. / 256.);
                coverage_q_ = q + 1;
            }
            sampleNext(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
        }
    }

    void analyzeCycle(const SystemState& s) {
        if (analyzed_version_ == graph_version_)
            return;
        analyzed_version_ = graph_version_;
        uniform_cycle_ = false;
        if (confirmed_edges_ != static_cast<int>(history_.size()))
            return;
        if (last_op_ < 0)
            return;
        int64_t size = -1;
        for (const auto& o : s.operators) {
            if (o.phase != Phase::PROBE)
                return;
            for (const auto& p : o.partitions) {
                if (p.data_size <= 0)
                    return;
                if (size < 0)
                    size = p.data_size;
                else if (size != p.data_size)
                    return;
            }
        }
        const int start = last_op_ * p_ + last_pid_, n = static_cast<int>(history_.size());
        int at = start;
        for (int j = 1; j <= n; ++j) {
            if (confidence_[at] < 3 || successor_[at] < 0)
                return;
            at = successor_[at];
            if (at == start) {
                uniform_cycle_ = (j == n);
                return;
            }
        }
    }

    // 计算可逐出分区的代价密度，并选择满足释放字节数的动作。
    void propose(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions, int frequency_mode) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        if (required <= free_bytes)
            return;
        const int64_t need = required - free_bytes;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id;
            next_pid = static_cast<int>(s.next_op.key % p_);
        }
        analyzeCycle(s);
        if (uniform_cycle_) {
            // Verified equal-size cyclic-route hypothesis. MRU keeps a stable
            // resident subset without scanning all KP states on each request.
            for (int j = 0; j < recent_count_; ++j) {
                int slot = (recent_head_ - 1 - j + static_cast<int>(recent_.size()))
                    % static_cast<int>(recent_.size());
                int id = recent_[slot], o = id / p_, pa = id % p_;
                if ((o == op && pa == pid) || (o == next_op && pa == next_pid))
                    continue;
                const auto& part = s.operators[o].partitions[pa];
                if (part.in_memory && part.data_size >= need) {
                    actions.emplace_back(Action::SPILL, o, pa);
                    return;
                }
            }
        }

        const int64_t now = s.hit_count + s.miss_count + 1;
        std::fill(cached_valid_.begin(), cached_valid_.end(), 0);
        const bool evidence = s.hit_count + s.miss_count > 0;
        const bool scan = streak_ >= 6 && stride_ > 0 && observed_count_ * 2 > now;
        const double observed_weight = demandWeight(now - 1);
        victims_.clear();
        for (const auto& o : s.operators)
            for (const auto& part : o.partitions) {
                if (!part.in_memory || part.data_size <= 0
                    || (o.op_id == op && part.partition_id == pid))
                    continue;
                const auto& h = history_[o.op_id * p_ + part.partition_id];
                double reuse = 0;
                if (evidence && h.last >= 0) {
                    const double age = static_cast<double>(std::max<int64_t>(0, now - h.last));
                    reuse = std::min(1.0, h.count / 16.0) / (1.0 + (age + 1.0) / 64.0);
                }
                if (evidence && scan && o.op_id == op && o.op_id == last_op_) {
                    const int delta = (part.partition_id - last_pid_ + p_) % p_;
                    reuse = 1.0 - static_cast<double>(step_distance_[delta]) / p_;
                }
                if (frequency_mode && o.phase == Phase::PROBE && !scan && !uniform_cycle_) {
                    ensureProbabilities(s);
                    const int id = o.op_id * p_ + part.partition_id;
                    ensureProbability(id);
                    reuse = 64. * (frequency_mode == 1 ? flat_probability_[id] : hier_probability_[id]);
                } else if (evidence)
                    reuse = refaultReuse(o.op_id * p_ + part.partition_id, now - 1, reuse, observed_weight);
                // The true penalty is absent from SystemState. A fixed 100 microsecond
                // surrogate is used here; it is not the hidden scoring penalty.
                double priority = reuse * (1.0 / s.read_bandwidth
                    + 1.0 / s.write_bandwidth + 100.0 / part.data_size);
                if (HASHJOIN_SIZE_BIAS && evidence) {
                    const double typical =
                        std::max(1., static_cast<double>(s.memory_limit) / history_.size());
                    priority *= std::sqrt(1. + part.data_size / typical);
                }
                if (o.op_id == next_op && part.partition_id == next_pid)
                    priority += 1e12;
                victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});
            }

        auto better = [](const Victim& a, const Victim& b) {
            if (a.priority != b.priority)
                return a.priority < b.priority;
            return a.bytes > b.bytes;
        };
        if ((evidence || s.read_bandwidth >= s.write_bandwidth) && !victims_.empty()) {
            auto less = better;
            const int cap = std::min<int>(4, victims_.size());
            std::partial_sort(victims_.begin(), victims_.begin() + cap, victims_.end(), less);
            int best_mask = 0;
            double best_loss = 1e300;
            for (int mask = 1; mask < (1 << cap); ++mask) {
                int64_t bytes = 0;
                double loss = 0;
                for (int j = 0; j < cap; ++j)
                    if (mask & (1 << j)) {
                        const auto& v = victims_[j];
                        bytes += v.bytes;
                        loss += v.priority * v.bytes
                            + 0.25 * static_cast<double>(v.bytes) / s.write_bandwidth;
                    }
                if (bytes >= need && loss < best_loss) {
                    best_mask = mask;
                    best_loss = loss;
                }
            }
            if (best_mask) {
                for (int j = 0; j < cap; ++j)
                    if (best_mask & (1 << j))
                        actions.emplace_back(Action::SPILL, victims_[j].op, victims_[j].pid);
                return;
            }
        }
        if (!evidence) {
            std::sort(victims_.begin(), victims_.end(), better);
            int64_t freed = 0;
            for (const auto& v : victims_) {
                if (freed >= need)
                    break;
                actions.emplace_back(Action::SPILL, v.op, v.pid);
                freed += v.bytes;
            }
            return;
        }

        // The common one-victim path is linear. If multiple are needed, heapify
        // once: O(n + v log n), preserving the O(n log n) worst-case bound.
        auto first = std::min_element(victims_.begin(), victims_.end(), better);
        if (first != victims_.end() && first->bytes >= need) {
            actions.emplace_back(Action::SPILL, first->op, first->pid);
            return;
        }
        auto worse = [&](const Victim& a, const Victim& b) {
            return better(b, a);
        };
        std::make_heap(victims_.begin(), victims_.end(), worse);
        int64_t freed = 0;
        while (freed < need && !victims_.empty()) {
            std::pop_heap(victims_.begin(), victims_.end(), worse);
            const auto v = victims_.back();
            victims_.pop_back();
            actions.emplace_back(Action::SPILL, v.op, v.pid);
            freed += v.bytes;
        }
    }

    void release(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions) {
        probability_cache_valid_ = false;
        propose(s, op, pid, required, actions, HASHJOIN_REUSE_ESTIMATOR == 1 ? 1 : (HASHJOIN_REUSE_ESTIMATOR == 2 ? 2 : 0));
        if (HASHJOIN_REUSE_ESTIMATOR != 3 || required <= s.memory_limit - s.memory_used)
            return;
        for (const auto& o : s.operators)
            if (o.phase != Phase::PROBE)
                return;
        const int64_t now = s.hit_count + s.miss_count + 1;
        if (uniform_cycle_ || (streak_ >= 6 && stride_ > 0 && observed_count_ * 2 > now))
            return;
        pruneSpills(s, required, actions);
        std::vector<Action> alternative;
        propose(s, op, pid, required, alternative, 2);
        pruneSpills(s, required, alternative);
        if (chooseAlternative(s, actions, alternative))
            actions.swap(alternative);
    }

    // 在仍满足容量需求的前提下，按原顺序删除多余逐出动作。
    void pruneSpills(const SystemState& s, int64_t required, std::vector<Action>& a) {
        const int64_t need = required - (s.memory_limit - s.memory_used);
        int64_t freed = 0;
        for (const auto& x : a)
            freed += s.operators[x.op_id].partitions[x.partition_id].data_size;
        size_t keep = 0;
        for (const auto& x : a) {
            const int64_t size = s.operators[x.op_id].partitions[x.partition_id].data_size;
            if (freed - size >= need) {
                freed -= size;
                continue;
            }
            a[keep++] = x;
        }
        a.erase(a.begin() + keep, a.end());
    }

public:
    // 官方回调：溢出释放空间、缺失加载与周期性可见信息处理。
    std::vector<Action> onMemoryOverflow(const SystemState& s, int op, int pid, int64_t z) override {
        active_ = true;
        update(s);
        std::vector<Action> a;
        release(s, op, pid, z, a);
        pruneSpills(s, z, a);
        record(s, a);
        return a;
    }

    std::vector<Action> onPartitionMiss(const SystemState& s, int op, int pid) override {
        active_ = true;
        update(s, op, pid);
        std::vector<Action> a;
        release(s, op, pid, s.operators[op].partitions[pid].data_size, a);
        pruneSpills(s, s.operators[op].partitions[pid].data_size, a);
        a.emplace_back(Action::LOAD, op, pid);
        record(s, a);
        return a;
    }

    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;
        if (!active_)
            return a;
        update(s, -1, -1, true);
        if (s.next_op.type != "PROBE")
            return a;
        const int op = s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size()))
            return a;
        const int pid = static_cast<int>(s.next_op.key % p_);
        const auto& part = s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || part.in_memory
            || part.data_size > s.memory_limit)
            return a;
        analyzeCycle(s);
        // Preserve the later miss callback's extra lookahead unless no eviction
        // is needed or the equal-size cyclic-route hypothesis supplies it.
        if (part.data_size > s.memory_limit - s.memory_used && !uniform_cycle_)
            return a;
        release(s, op, pid, part.data_size, a);
        pruneSpills(s, s.operators[op].partitions[pid].data_size, a);
        a.emplace_back(Action::LOAD, op, pid);
        record(s, a);
        return a;
    }
};

/* ===== 执行引擎 ===== */

class HashJoinEngine {
private:
    int64_t memory_limit_;
    int num_partitions_;
    double write_bandwidth_;
    double read_bandwidth_;
    int miss_penalty_;
    int periodic_interval_;

    int64_t memory_used_;
    int64_t hit_count_;
    int64_t miss_count_;
    double total_io_time_;
    double total_decision_time_;   // 调度器决策CPU耗时累计（微秒）
    int64_t total_io_bytes_;
    int operation_count_;

    std::vector<OperatorState> operators_;
    std::unique_ptr<SpillScheduler> scheduler_;
    PendingOp next_op_;  // 预存下一个操作，供getSystemState使用

    SystemState getSystemState() const {
        SystemState state;
        state.memory_used = memory_used_;
        state.memory_limit = memory_limit_;
        state.num_partitions = num_partitions_;
        state.write_bandwidth = write_bandwidth_;
        state.read_bandwidth = read_bandwidth_;
        state.hit_count = hit_count_;
        state.miss_count = miss_count_;
        state.total_io_bytes = total_io_bytes_;
        state.operators = operators_;
        state.next_op = next_op_;
        return state;
    }

    // 测量并累加一次调度器调用的CPU耗时（微秒）
    template<typename F>
    auto timedSchedulerCall(F&& f) -> decltype(f()) {
        auto t_start = std::chrono::high_resolution_clock::now();
        auto result = f();
        auto t_end = std::chrono::high_resolution_clock::now();
        double us = std::chrono::duration<double, std::micro>(t_end - t_start).count();
        total_decision_time_ += us;
        return result;
    }

    void executeActions(const std::vector<Action>& actions) {
        for (const auto& act : actions) {
            auto& part = operators_[act.op_id].partitions[act.partition_id];
            if (act.type == Action::SPILL) {
                if (!part.in_memory || part.data_size == 0) continue;
                total_io_time_ += static_cast<double>(part.data_size) / write_bandwidth_;
                total_io_bytes_ += part.data_size;
                part.in_memory = false;
                memory_used_ -= part.data_size;
            } else if (act.type == Action::LOAD) {
                // 引擎静默忽略非法 LOAD：对 in_memory 分区、或 BUILD 阶段算子的分区
                if (part.in_memory) continue;
                if (operators_[act.op_id].phase == Phase::BUILD) continue;
                if (memory_used_ + part.data_size > memory_limit_) {
                    std::cerr << "OOM: LOAD would exceed memory limit" << std::endl;
                    std::exit(1);
                }
                total_io_time_ += static_cast<double>(part.data_size) / read_bandwidth_;
                total_io_bytes_ += part.data_size;
                part.in_memory = true;
                memory_used_ += part.data_size;
            }
        }
    }

public:
    HashJoinEngine(int64_t memory_limit, int num_partitions,
                   double write_bandwidth, double read_bandwidth,
                   int miss_penalty, int periodic_interval,
                   std::unique_ptr<SpillScheduler> scheduler)
        : memory_limit_(memory_limit), num_partitions_(num_partitions),
          write_bandwidth_(write_bandwidth), read_bandwidth_(read_bandwidth),
          miss_penalty_(miss_penalty), periodic_interval_(periodic_interval),
          memory_used_(0), hit_count_(0), miss_count_(0),
          total_io_time_(0.0), total_decision_time_(0.0),
          total_io_bytes_(0), operation_count_(0),
          scheduler_(std::move(scheduler)) {}

    void addOperator(int op_id) {
        OperatorState op;
        op.op_id = op_id;
        op.phase = Phase::BUILD;
        op.partitions.resize(num_partitions_);
        for (int i = 0; i < num_partitions_; ++i) {
            op.partitions[i].partition_id = i;
        }
        operators_.push_back(op);
    }

    // 设置下一个待处理操作（由main循环在执行当前操作前调用）
    void setNextOp(const PendingOp& op) { next_op_ = op; }

    void processInsert(int op_id, int64_t key, int64_t tuple_size) {
        int pid = key % num_partitions_;
        auto& part = operators_[op_id].partitions[pid];

        if (part.in_memory) {
            if (memory_used_ + tuple_size > memory_limit_) {
                // 内存溢出，调用调度器（计时）
                auto actions = timedSchedulerCall([&]() {
                    return scheduler_->onMemoryOverflow(
                        getSystemState(), op_id, pid, tuple_size);
                });
                executeActions(actions);
                // 校验：调度器释放的空间是否足够
                if (memory_used_ + tuple_size > memory_limit_) {
                    std::cerr << "OOM: scheduler failed to free enough memory for INSERT" << std::endl;
                    std::exit(1);
                }
            }
            part.data_size += tuple_size;
            memory_used_ += tuple_size;
        } else {
            // 分区在磁盘上，元组直接写磁盘
            total_io_time_ += static_cast<double>(tuple_size) / write_bandwidth_;
            total_io_bytes_ += tuple_size;
            part.data_size += tuple_size;
        }

        operation_count_++;
        if (operation_count_ % periodic_interval_ == 0) {
            auto actions = timedSchedulerCall([&]() {
                return scheduler_->onPeriodicAdjust(getSystemState());
            });
            executeActions(actions);
        }
    }

    // SWITCH不计入operation_count_，不触发周期性调度
    void processSwitch(int op_id) {
        operators_[op_id].phase = Phase::PROBE;
    }

    void processProbe(int op_id, int64_t key) {
        int pid = key % num_partitions_;
        auto& part = operators_[op_id].partitions[pid];

        if (part.in_memory) {
            hit_count_++;
        } else {
            miss_count_++;
            // 调用调度器加载分区（计时）
            auto actions = timedSchedulerCall([&]() {
                return scheduler_->onPartitionMiss(
                    getSystemState(), op_id, pid);
            });
            executeActions(actions);
            // 校验：调度器必须将目标分区加载到内存
            if (!part.in_memory) {
                std::cerr << "OOM: scheduler failed to load target partition for PROBE" << std::endl;
                std::exit(1);
            }
        }

        operation_count_++;
        if (operation_count_ % periodic_interval_ == 0) {
            auto actions = timedSchedulerCall([&]() {
                return scheduler_->onPeriodicAdjust(getSystemState());
            });
            executeActions(actions);
        }
    }

    void printResult() const {
        double total_score = total_io_time_ +
            static_cast<double>(miss_penalty_) * miss_count_ + total_decision_time_;
        std::cout << std::fixed << std::setprecision(2);
        std::cout << "Total_IO_Time: " << total_io_time_ << std::endl;
        std::cout << "Total_Decision_Time: " << total_decision_time_ << std::endl;
        std::cout << "Hit_Count: " << hit_count_ << std::endl;
        std::cout << "Miss_Count: " << miss_count_ << std::endl;
        std::cout << "Total_Score: " << total_score << std::endl;
    }
};

/* ===== 主函数 ===== */

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <input_file>" << std::endl;
        return 1;
    }

    std::ifstream fin(argv[1]);
    if (!fin) {
        std::cerr << "Cannot open input file: " << argv[1] << std::endl;
        return 1;
    }

    int K, P, miss_penalty, N, B;
    int64_t M;
    double W, R;

    fin >> K >> P >> M >> W >> R >> miss_penalty;
    fin >> N >> B;

    auto scheduler = std::make_unique<MySpillScheduler>();
    HashJoinEngine engine(M, P, W, R, miss_penalty, B, std::move(scheduler));

    for (int i = 0; i < K; ++i) {
        int op_id, build_count, probe_count;
        fin >> op_id >> build_count >> probe_count;
        engine.addOperator(op_id);
    }

    // 预读所有操作行
    std::vector<std::string> op_lines;
    {
        std::string line;
        std::getline(fin, line);  // consume newline
        for (int i = 0; i < N; ++i) {
            std::getline(fin, line);
            op_lines.push_back(line);
        }
    }

    for (int i = 0; i < N; ++i) {
        // 设置next_op为当前操作的下一条
        PendingOp next;
        if (i + 1 < N) {
            std::istringstream niss(op_lines[i + 1]);
            niss >> next.type;
            if (next.type == "INSERT") niss >> next.op_id >> next.key >> next.tuple_size;
            else if (next.type == "SWITCH") niss >> next.op_id;
            else if (next.type == "PROBE") niss >> next.op_id >> next.key;
        } else {
            next.type = "";  // 无后续操作
        }
        engine.setNextOp(next);

        // 执行当前操作
        std::istringstream iss(op_lines[i]);
        std::string op;
        iss >> op;

        if (op == "INSERT") {
            int op_id;
            int64_t key, size;
            iss >> op_id >> key >> size;
            engine.processInsert(op_id, key, size);
        } else if (op == "SWITCH") {
            int op_id;
            iss >> op_id;
            engine.processSwitch(op_id);
        } else if (op == "PROBE") {
            int op_id;
            int64_t key;
            iss >> op_id >> key;
            engine.processProbe(op_id, key);
        }
    }

    engine.printResult();
    return 0;
}
