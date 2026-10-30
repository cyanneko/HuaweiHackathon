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

class R53BestFit : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&idBefore(a,b));}
 static bool ordered(const Candidate& a,const Candidate& b){return a.size<b.size||(a.size==b.size&&(a.op>b.op||(a.op==b.op&&a.pid>b.pid)));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  std::vector<Action> actions;int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const int64_t deficit=need-available;Candidate maximum{},fit{};bool haveMaximum=false,haveFit=false;
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id};
    if(!haveMaximum||larger(c,maximum)){maximum=c;haveMaximum=true;}
    if(c.size>=deficit&&(!haveFit||c.size<fit.size||(c.size==fit.size&&idBefore(c,fit)))){fit=c;haveFit=true;}
   }
   if(haveMaximum){
    const Candidate first=haveFit?fit:maximum;actions.emplace_back(Action::SPILL,first.op,first.pid);available+=first.size;
    if(available<need){
     std::vector<Candidate> pool;pool.reserve(s.operators.size()*s.num_partitions);
     for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)&&!(o.op_id==first.op&&p.partition_id==first.pid))pool.push_back({p.data_size,o.op_id,p.partition_id});
     std::sort(pool.begin(),pool.end(),ordered);
     while(available<need&&!pool.empty()){
      const int64_t remaining=need-available;
      auto sufficient=std::lower_bound(pool.begin(),pool.end(),remaining,[](const Candidate& c,int64_t n){return c.size<n;});
      if(sufficient!=pool.end()){
       auto end=std::upper_bound(sufficient,pool.end(),sufficient->size,[](int64_t n,const Candidate& c){return n<c.size;});
       const auto c=*(end-1);actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;break;
      }
      const auto c=pool.back();pool.pop_back();actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;
     }
    }
   }
  }
  if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};
// Requires the official framework and the frozen R53BestFit class before this class.
// Fixed local surrogate: a PROBE victim costs one write plus one future reload.
class R56SingleFitPhase : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;bool probe;};
 struct Representative {Candidate value{};bool present=false;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static void record(Representative& r,const Candidate& c){
  if(!r.present||c.size<r.value.size||(c.size==r.value.size&&idBefore(c,r.value))){r.value=c;r.present=true;}
 }
 static bool preferable(const Candidate& a,const Candidate& b,double probeCoefficient){
  // Algebraic same-phase ordering preserves the smallest sufficient byte size.
  if(a.probe==b.probe)return a.size<b.size||(a.size==b.size&&idBefore(a,b));
  const double x=static_cast<double>(a.size)*(a.probe?probeCoefficient:1.0);
  const double y=static_cast<double>(b.size)*(b.probe?probeCoefficient:1.0);
  return x<y||(x==y&&(a.size<b.size||(a.size==b.size&&idBefore(a,b))));
 }
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  const int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const int64_t deficit=need-available;
   const bool nextProbe=s.next_op.type=="PROBE";
   const int nextOp=nextProbe?s.next_op.op_id:-1;
   const int nextPid=nextProbe?static_cast<int>(s.next_op.key%s.num_partitions):-1;
   Representative all[2],safe[2];
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id,o.phase==Phase::PROBE};
    const int phase=c.probe?1:0;record(all[phase],c);
    if(!nextProbe||c.op!=nextOp||c.pid!=nextPid)record(safe[phase],c);
   }
   if(!all[0].present&&!all[1].present){
    // No sufficient individual: retain the complete original R53 plan,
    // including its dynamic deficit updates, ties and final LOAD.
    R53BestFit fallback;
    return miss?fallback.onPartitionMiss(s,op,pid):fallback.onMemoryOverflow(s,op,pid,need);
   }
   const Representative* reps=(safe[0].present||safe[1].present)?safe:all;
   Candidate selected=reps[0].present?reps[0].value:reps[1].value;
   if(reps[0].present&&reps[1].present&&preferable(reps[1].value,selected,1.0+s.write_bandwidth/s.read_bandwidth))selected=reps[1].value;
   std::vector<Action> actions;actions.emplace_back(Action::SPILL,selected.op,selected.pid);
   if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
  }
  std::vector<Action> actions;if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t need)override{return choose(s,op,pid,need,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid)override{return choose(s,op,pid,s.operators[op].partitions[pid].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

class MySpillScheduler:public R56SingleFitPhase{};

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
