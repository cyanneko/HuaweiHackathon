#include <algorithm>
#include <cmath>
#include <vector>
#include <cstdint>
// Observer-only serialization; never receives a reference to the live scheduler.
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
namespace obs11 {
inline void require(bool ok,const char* message) {
    if(!ok){std::cerr << "OBS_ERROR " << message << '\n';std::abort();}
}
inline void number(std::ostream& out,double value) {
    require(std::isfinite(value),"nonfinite snapshot value");out << value;
}
inline void actions(std::ostream& out,const std::vector<Action>& values) {
    out << '[';bool comma=false;
    for(const auto& x:values){if(comma)out << ',';comma=true;
        out << "[\"" << (x.type==Action::SPILL?'S':'L') << "\"," << x.op_id << ',' << x.partition_id << ']';}
    out << ']';
}
inline bool same(const std::vector<Action>& a,const std::vector<Action>& b) {
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)
        if(a[i].type!=b[i].type || a[i].op_id!=b[i].op_id || a[i].partition_id!=b[i].partition_id)return false;
    return true;
}
inline void state(std::ostream& out,const SystemState& s) {
    out << "{\"memory_used\":" << s.memory_used << ",\"memory_limit\":" << s.memory_limit
        << ",\"num_partitions\":" << s.num_partitions << ",\"write_bandwidth\":";
    number(out,s.write_bandwidth);out << ",\"read_bandwidth\":";number(out,s.read_bandwidth);
    out << ",\"hit_count\":" << s.hit_count << ",\"miss_count\":" << s.miss_count
        << ",\"total_io_bytes\":" << s.total_io_bytes << ",\"next_op\":{\"type\":\"" << s.next_op.type
        << "\",\"op_id\":" << s.next_op.op_id << ",\"key\":" << s.next_op.key
        << ",\"tuple_size\":" << s.next_op.tuple_size << "},\"operators\":[";
    bool comma=false;
    for(const auto& o:s.operators){if(comma)out << ',';comma=true;
        out << "{\"op_id\":" << o.op_id << ",\"phase\":\"" << (o.phase==Phase::PROBE?"PROBE":"BUILD") << "\",\"partitions\":[";
        bool pc=false;for(const auto& p:o.partitions){if(pc)out << ',';pc=true;
            out << "{\"partition_id\":" << p.partition_id << ",\"data_size\":" << p.data_size
                << ",\"in_memory\":" << (p.in_memory?"true":"false") << '}';}
        out << "]}";
    }
    out << "]}";
}
}

#define R80_MODE 2
#define R79_ADAPTIVE 1
#define R74_MODE 3
#define R74_SIZE 0
// Submit this class (and standard-library includes) after the official declarations.
// No input access, engine changes, training, external data, or C++17 features.
#include <algorithm>
#include <cstdint>
#include <vector>
#include <cmath>
#include <array>
#include <cstdint>
namespace r74 {
inline double decay(int64_t delta) {
 // Lazy initialization occurs inside the first real Risk.advance call.
 // Direct exp evaluation preserves the original expression per entry.
 static const std::array<double,1025> table=[]() {
  std::array<double,1025> values{};
  for(int i=0;i<=1024;++i)values[i]=std::exp(-static_cast<double>(i)/512.);
  return values;
 }();
 return delta>=0 && delta<=1024 ? table[static_cast<std::size_t>(delta)]
     : std::exp(-static_cast<double>(delta)/512.);
}

struct Risk {
 double exposure=0, events=0, starts=0; int active=0; int64_t last=0;
 void advance(int64_t q) {
  if(q<=last)return;
  if(!active && exposure==0. && events==0. && starts==0.) {last=q;return;}
  const double f=decay(q-last);
  exposure=exposure*f+active*512.*(1.-f);
  events*=f; starts*=f; last=q;
 }
 void begin(int64_t q) {advance(q); ++active; ++starts;}
 void end(int64_t q,bool event) {advance(q); --active; if(event)++events;}
 double mean(int64_t q,double prior=64.) {advance(q); return (exposure+prior)/(events+1.);}
};
}

#include <cmath>
#include <array>
#include <cstdint>
namespace r75op {
inline double decay(int64_t delta) {
 // Lazy initialization occurs inside the first real Risk.advance call.
 // Direct exp evaluation preserves the original expression per entry.
 static const std::array<double,1025> table=[]() {
  std::array<double,1025> values{};
  for(int i=0;i<=1024;++i)values[i]=std::exp(-static_cast<double>(i)/128.);
  return values;
 }();
 return delta>=0 && delta<=1024 ? table[static_cast<std::size_t>(delta)]
     : std::exp(-static_cast<double>(delta)/128.);
}

struct Risk {
 double exposure=0, events=0, starts=0; int active=0; int64_t last=0;
 void advance(int64_t q) {
  if(q<=last)return;
  if(!active && exposure==0. && events==0. && starts==0.) {last=q;return;}
  const double f=decay(q-last);
  exposure=exposure*f+active*128.*(1.-f);
  events*=f; starts*=f; last=q;
 }
 void begin(int64_t q) {advance(q); ++active; ++starts;}
 void end(int64_t q,bool event) {advance(q); --active; if(event)++events;}
 double mean(int64_t q,double prior=64.) {advance(q); return (exposure+prior)/(events+1.);}
};
}

class R80ObservedReference : public SpillScheduler {
    bool probability_cache_valid_=false;
    int64_t probability_clock_=0;
    double probability_total_=0.,probability_weight2_=0.;
    std::vector<double> flat_probability_,hier_probability_;
    std::vector<uint64_t> probability_tags_;
    uint64_t probability_epoch_=0;
    double probability_prior_=0.,probability_denom_=1.;
    std::vector<int> changed_sign_,changed_ids_;
    static double probabilityDecay(int64_t delta) {
        static const std::array<double,8193> table=[]() {
            std::array<double,8193> values{};
            for(int i=0;i<=8192;++i)values[i]=nextDecay(i);
            return values;
        }();
        return delta>=0 && delta<=8192 ? table[static_cast<std::size_t>(delta)] : nextDecay(delta);
    }
    void ensureProbabilities(const SystemState& s) {
        if(probability_cache_valid_)return;
        const int n=static_cast<int>(next_mass_.size());
        probability_clock_=std::max(s.hit_count+s.miss_count,next_sample_q_);
        probability_total_=probability_weight2_=0.;
        for(int op=0;op<static_cast<int>(sharing_.size());++op) {
            refreshSharing(op,probability_clock_);
            probability_total_+=sharing_[op].mass;probability_weight2_+=sharing_[op].weight2;
        }
        flat_probability_.resize(n);hier_probability_.resize(n);
        if(static_cast<int>(changed_sign_.size())!=n)changed_sign_.assign(n,0);
        if(static_cast<int>(probability_tags_.size())!=n)probability_tags_.assign(n,0);
        if(++probability_epoch_==0) {
            std::fill(probability_tags_.begin(),probability_tags_.end(),0);
            probability_epoch_=1;
        }
        probability_prior_=64./n;probability_denom_=probability_total_+64.;
        probability_cache_valid_=true;
    }
    void ensureProbability(int id) {
        if(probability_tags_[id]==probability_epoch_)return;
        const auto& c=next_mass_[id];const auto& g=sharing_[id/p_];
        const double mass=c.mass==0. ? 0. : c.mass*probabilityDecay(std::max<int64_t>(0,probability_clock_-c.last));
        flat_probability_[id]=(mass+probability_prior_)/probability_denom_;
        hier_probability_[id]=((1.-g.share)*mass+g.share*g.mass/p_+probability_prior_)/probability_denom_;
        probability_tags_[id]=probability_epoch_;
    }
    struct PairDelta {double immediate=0.,mean=0.,second=0.,sd=0.;bool different=false;};
    PairDelta comparePlans(const SystemState& s,const std::vector<Action>& base,const std::vector<Action>& alt) {
        ensureProbabilities(s);changed_ids_.clear();
        for(const auto& a:base) {const int id=a.op_id*p_+a.partition_id;if(changed_sign_[id]==0)changed_ids_.push_back(id);--changed_sign_[id];}
        for(const auto& a:alt) {const int id=a.op_id*p_+a.partition_id;if(changed_sign_[id]==0)changed_ids_.push_back(id);++changed_sign_[id];}
        PairDelta d;
        for(int id:changed_ids_) {
            const int sign=changed_sign_[id];changed_sign_[id]=0;if(!sign)continue;
            d.different=true;const int op=id/p_,pid=id%p_;
            const double bytes=s.operators[op].partitions[pid].data_size;
            const double coefficient=sign*(bytes/s.read_bandwidth+bytes/s.write_bandwidth+100.);
            d.immediate+=sign*bytes/s.write_bandwidth;
            if(s.next_op.type=="PROBE" && s.next_op.op_id==op && s.next_op.key%p_==pid)
                d.immediate+=sign*(bytes/s.read_bandwidth+100.);
            ensureProbability(id);
            d.mean+=flat_probability_[id]*coefficient;d.second+=flat_probability_[id]*coefficient*coefficient;
        }
        const double effective=probability_weight2_>0. ? probability_total_*probability_total_/probability_weight2_ : 0.;
        d.sd=64.*std::sqrt(std::max(0.,d.second-d.mean*d.mean)/(effective+1.));
        return d;
    }
    bool chooseAlternative(const SystemState& s,const std::vector<Action>& base,const std::vector<Action>& alt) {
        ensureProbabilities(s);
        if(!(probability_total_>0.) || !(probability_weight2_>0.))return false;
        const auto d=comparePlans(s,base,alt);
        return d.different && d.immediate+64.*d.mean+2.*d.sd<0.;
    }

    struct ShareGroup {
        double mass=0., squares=0., weight2=0., heterogeneity=0., share=.75;
        int64_t last=0;
    };
    struct NextMass { double mass=0.; int64_t last=0; };
    std::vector<ShareGroup> sharing_;
    std::vector<NextMass> next_mass_;
    int64_t next_sample_q_=-1;
    static double nextDecay(int64_t d) {
        return std::exp(-0.693147180559945309417232121458176568*static_cast<double>(d)/2048.);
    }
    void refreshSharing(int op,int64_t q) {
        auto& g=sharing_[op];
        if(q>g.last) {
            const double f=nextDecay(q-g.last);
            g.mass*=f; g.squares*=f*f; g.weight2*=f*f; g.last=q;
        }
        g.heterogeneity=0.; g.share=.75;
        if(p_<=1 || !(g.mass>8.) || !(g.weight2>1e-200) ||
           !std::isfinite(g.mass) || !std::isfinite(g.squares) || !std::isfinite(g.weight2)) return;
        const double ss=g.mass*g.mass, n=ss/g.weight2;
        if(!(n>8.) || !std::isfinite(n) || !std::isfinite(ss)) return;
        const double v=std::max(0.,(p_*g.squares/ss-1.-(p_-1)/n)/(1.-1./n));
        const double strength=v*(g.mass-8.)/(g.mass+p_);
        if(std::isfinite(strength)) {g.heterogeneity=strength/(1.+strength);g.share=.75/(1.+strength);}
    }
    void sampleNext(int op,int pid,int64_t ordinal) {
        refreshSharing(op,ordinal);
        if(ordinal<=next_sample_q_)return;
        auto& g=sharing_[op]; auto& c=next_mass_[op*p_+pid];
        if(g.last>c.last)c.mass*=nextDecay(g.last-c.last);
        c.last=g.last;
        g.squares+=2.*c.mass+1.; g.mass+=1.; g.weight2+=1.; c.mass+=1.;
        next_sample_q_=ordinal;
        refreshSharing(op,g.last);
    }
    double partitionBase(int id,int64_t q,double visible) {
        auto& r=risk_[id];r.advance(q);
        if(r.starts<1e-9)return visible;
        return 64./(64.+r.mean(q,64.));
    }


    struct Intent {int id; int64_t q, size; bool spill;};
    std::vector<r74::Risk> risk_; std::vector<r75op::Risk> operator_risk_;
    std::vector<double> cached_priors_; std::vector<unsigned char> cached_valid_;
    std::vector<Intent> intents_;
    double coverage_=0.;
    int64_t coverage_q_=0;
    void confirm(const SystemState& s) {
        for(const auto& i:intents_) {
            const int o=i.id/p_, p=i.id%p_;
            const auto& part=s.operators[o].partitions[p];
            if(part.data_size!=i.size)continue;
            auto& r=risk_[i.id]; auto& pooled=operator_risk_[o];
            if(i.spill && !part.in_memory && !r.active) {
                r.begin(i.q); pooled.begin(i.q);
            } else if(!i.spill && part.in_memory && r.active) {
                r.end(i.q,false); pooled.end(i.q,false);
            }
        }
        intents_.clear();
    }
    void record(const SystemState& s,const std::vector<Action>& actions) {
        const int64_t q=s.hit_count+s.miss_count;
        for(const auto& a:actions) {
            const auto& o=s.operators[a.op_id];
            const auto& p=o.partitions[a.partition_id];
            if(o.phase!=Phase::PROBE || p.data_size<=0)continue;
            if(a.type==Action::SPILL && p.in_memory)
                intents_.push_back({a.op_id*p_+a.partition_id,q,p.data_size,true});
            else if(a.type==Action::LOAD && !p.in_memory)
                intents_.push_back({a.op_id*p_+a.partition_id,q,p.data_size,false});
        }
    }
    double demandWeight(int64_t q) const {
        if(R74_MODE<3)return .25;
        const double elapsed=static_cast<double>(std::max<int64_t>(1,q));
        const double cov=std::min(1.,coverage_*std::exp(-static_cast<double>(std::max<int64_t>(0,q-coverage_q_))/256.)/(1.-std::exp(-elapsed/256.)));
        return cov>=.75 ? 1. : .25;
    }
    double refaultReuse(int id,int64_t q,double visible,double observed_weight) {
        if(observed_weight>=1.)return visible;
        const double part=partitionBase(id,q,visible);
        const int op=id/p_; auto& pool=operator_risk_[op];
        if(!cached_valid_[op]) {pool.advance(q);cached_priors_[op]=pool.mean(q,64.);refreshSharing(op,q);cached_valid_[op]=1;}
        double reuse=part;
        if(pool.starts>=1e-9) {
            const double alpha=R79_ADAPTIVE ? sharing_[op].share : .75;
            const double pooled=64./(64.+cached_priors_[op]);
            reuse=(1.-alpha)*part+alpha*pooled;
        }
        return (1.-observed_weight)*reuse+observed_weight*visible;
    }

    struct History { int64_t last = -1; double count = 0; };
    struct Victim { int op, pid; int64_t bytes; double priority; };
    std::vector<History> history_;
    std::vector<Victim> victims_;
    std::vector<int> step_distance_;
    std::vector<int> successor_, confidence_, recent_;
    int recent_head_=0, recent_count_=0;
    int64_t graph_version_=0, analyzed_version_=-1;
    bool uniform_cycle_=false;
    int confirmed_edges_=0;
    bool active_ = false;
    int p_ = 0, cached_stride_ = -1;
    int64_t observed_q_ = -1, observed_count_ = 0;
    int last_op_ = -1, last_pid_ = -1, stride_ = -1, streak_ = 0;
    void observe(int op, int pid, int64_t q) {
        if (q <= observed_q_) return;
        const int current_id=op*p_+pid;
        if (q==observed_q_+1 && last_op_>=0) {
            const int previous_id=last_op_*p_+last_pid_;
            if (successor_[previous_id]==current_id) {
                confidence_[previous_id]=std::min(7,confidence_[previous_id]+1);
                if (confidence_[previous_id]==3) {++graph_version_;++confirmed_edges_;}
             } else {
                if(confidence_[previous_id]>=3)--confirmed_edges_;
                successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;
            }
        }
        recent_[recent_head_]=current_id;
        recent_head_=(recent_head_+1)%static_cast<int>(recent_.size());
        recent_count_=std::min(recent_count_+1,static_cast<int>(recent_.size()));
        auto& h = history_[op * p_ + pid];
        if (h.last >= 0)
            h.count *= 256.0 / (256.0 + static_cast<double>(q - h.last));
        h.count += 1; h.last = q;
        if (q == observed_q_ + 1 && op == last_op_) {
            const int delta = (pid - last_pid_ + p_) % p_;
            if (delta != 0 && delta == stride_) ++streak_;
            else { stride_ = delta; streak_ = 1; }
        } else { stride_ = -1; streak_ = 0; }
        last_op_ = op; last_pid_ = pid;
        observed_q_ = q; ++observed_count_;
        if (streak_ >= 3 && stride_ > 0 && cached_stride_ != stride_) {
            step_distance_.assign(p_, p_);
            int at = 0;
            for (int j = 1; j <= p_; ++j) {
                at = (at + stride_) % p_;
                if (step_distance_[at] == p_) step_distance_[at] = j;
            }
            cached_stride_ = stride_;
        }
    }
    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {
        const int n = static_cast<int>(s.operators.size()) * s.num_partitions;
        if (p_ != s.num_partitions || static_cast<int>(history_.size()) != n) {
            p_ = s.num_partitions; history_.assign(n, History{});
            risk_.assign(n,r74::Risk{}); operator_risk_.assign(s.operators.size(),r75op::Risk{});
            sharing_.assign(s.operators.size(),ShareGroup{});next_mass_.assign(n,NextMass{});next_sample_q_=-1;
            intents_.clear(); coverage_=0.; coverage_q_=0; cached_priors_.assign(s.operators.size(),64.); cached_valid_.assign(s.operators.size(),0);
            successor_.assign(n,-1);confidence_.assign(n,0);recent_.assign(n+2,-1);
            recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;confirmed_edges_=0;
            observed_q_ = -1; observed_count_ = 0;
            last_op_ = last_pid_ = stride_ = cached_stride_ = -1; streak_ = 0;
        }
        const int64_t q = s.hit_count + s.miss_count;
        confirm(s);
        // The engine increments miss_count before this callback. Refault is
        // independent of next-op observation deduplication.
        if(op>=0) {
            auto& r=risk_[op*p_+pid];
            if(r.active) {r.end(q,true); operator_risk_[op].end(q,true);}
        }
        // A miss and its periodic callback may expose the same pending request.
        // Probe ordinals deduplicate those, while preserving real repeated keys.
        if (op >= 0) {refreshSharing(op,q);observe(op,pid,q);}
        if (s.next_op.type == "PROBE" && s.next_op.op_id >= 0 &&
            s.next_op.op_id < static_cast<int>(s.operators.size()))
        {
            if(periodic && q+1>coverage_q_) {
                coverage_*=std::exp(-static_cast<double>(q+1-coverage_q_)/256.);
                coverage_+=1.-std::exp(-1./256.); coverage_q_=q+1;
            }
            sampleNext(s.next_op.op_id,static_cast<int>(s.next_op.key % p_),q+1);
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
        }
    }
    void analyzeCycle(const SystemState& s) {
        if (analyzed_version_==graph_version_) return;
        analyzed_version_=graph_version_;uniform_cycle_=false;
        if(confirmed_edges_!=static_cast<int>(history_.size()))return;
        if (last_op_<0) return;
        int64_t size=-1;
        for (const auto& o:s.operators) {
            if (o.phase!=Phase::PROBE) return;
            for (const auto& p:o.partitions) {
                if (p.data_size<=0) return;
                if (size<0) size=p.data_size;
                else if (size!=p.data_size) return;
            }
        }
        const int start=last_op_*p_+last_pid_,n=static_cast<int>(history_.size());
        int at=start;
        for (int j=1;j<=n;++j) {
            if (confidence_[at]<3 || successor_[at]<0) return;
            at=successor_[at];
            if (at==start) {uniform_cycle_=(j==n);return;}
        }
    }
    void propose(const SystemState& s, int op, int pid, int64_t required,
                 std::vector<Action>& actions,int frequency_mode) {
        const int64_t free_bytes = s.memory_limit - s.memory_used;
        if (required <= free_bytes) return;
        const int64_t need = required - free_bytes;
        int next_op = -1, next_pid = -1;
        if (s.next_op.type == "PROBE") {
            next_op = s.next_op.op_id; next_pid = static_cast<int>(s.next_op.key % p_);
        }
        analyzeCycle(s);
        if (uniform_cycle_) {
            // Verified equal-size cyclic-route hypothesis. MRU keeps a stable
            // resident subset without scanning all KP states on each request.
            for (int j=0;j<recent_count_;++j) {
                int slot=(recent_head_-1-j+static_cast<int>(recent_.size()))%static_cast<int>(recent_.size());
                int id=recent_[slot],o=id/p_,pa=id%p_;
                if ((o==op && pa==pid) || (o==next_op && pa==next_pid)) continue;
                const auto& part=s.operators[o].partitions[pa];
                if (part.in_memory && part.data_size>=need) {
                    actions.emplace_back(Action::SPILL,o,pa);return;
                }
            }
        }
        const int64_t now = s.hit_count + s.miss_count + 1;
        std::fill(cached_valid_.begin(),cached_valid_.end(),0);
        const bool evidence = s.hit_count + s.miss_count > 0;
        const bool scan = streak_ >= 6 && stride_ > 0 &&
            observed_count_ * 2 > now;
        const double observed_weight=demandWeight(now-1);
        victims_.clear();
        for (const auto& o : s.operators) for (const auto& part : o.partitions) {
            if (!part.in_memory || part.data_size <= 0 ||
                (o.op_id == op && part.partition_id == pid)) continue;
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
            if(frequency_mode && o.phase==Phase::PROBE && !scan && !uniform_cycle_) {
                ensureProbabilities(s);const int id=o.op_id*p_+part.partition_id;ensureProbability(id);
                reuse=64.*(frequency_mode==1?flat_probability_[id]:hier_probability_[id]);
            } else if(evidence)reuse=refaultReuse(o.op_id*p_+part.partition_id,now-1,reuse,observed_weight);
            // The true penalty is absent from SystemState. A fixed 100 microsecond
            // surrogate is used here; it is not the hidden scoring penalty.
            double priority = reuse * (1.0 / s.read_bandwidth +
                1.0 / s.write_bandwidth + 100.0 / part.data_size);
            if(R74_SIZE && evidence) {
                const double typical=std::max(1.,static_cast<double>(s.memory_limit)/history_.size());
                priority*=std::sqrt(1.+part.data_size/typical);
            }
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;
            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority});
        }
        auto better = [](const Victim& a, const Victim& b) {
            if (a.priority != b.priority) return a.priority < b.priority;
            return a.bytes > b.bytes;
        };
        if ((evidence || s.read_bandwidth>=s.write_bandwidth) && !victims_.empty()) {
            auto less=better;
            const int cap=std::min<int>(4,victims_.size());
            std::partial_sort(victims_.begin(),victims_.begin()+cap,victims_.end(),less);
            int best_mask=0;double best_loss=1e300;
            for(int mask=1;mask<(1<<cap);++mask) {
                int64_t bytes=0;double loss=0;
                for(int j=0;j<cap;++j) if(mask&(1<<j)) {
                    const auto& v=victims_[j];bytes+=v.bytes;
                    loss+=v.priority*v.bytes+0.25*static_cast<double>(v.bytes)/s.write_bandwidth;
                }
                if(bytes>=need && loss<best_loss) {best_mask=mask;best_loss=loss;}
            }
            if(best_mask) {
                for(int j=0;j<cap;++j) if(best_mask&(1<<j))
                    actions.emplace_back(Action::SPILL,victims_[j].op,victims_[j].pid);
                return;
            }
        }
        if (!evidence) {
            std::sort(victims_.begin(),victims_.end(),better);
            int64_t freed=0;
            for (const auto& v:victims_) {
                if (freed>=need) break;
                actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            return;
        }
        // The common one-victim path is linear. If multiple are needed, heapify
        // once: O(n + v log n), preserving the O(n log n) worst-case bound.
        auto first=std::min_element(victims_.begin(),victims_.end(),better);
        if (first!=victims_.end() && first->bytes>=need) {
            actions.emplace_back(Action::SPILL,first->op,first->pid);return;
        }
        auto worse = [&](const Victim& a,const Victim& b){return better(b,a);};
        std::make_heap(victims_.begin(),victims_.end(),worse);
        int64_t freed=0;
        while (freed<need && !victims_.empty()) {
            std::pop_heap(victims_.begin(),victims_.end(),worse);
            const auto v=victims_.back();victims_.pop_back();
            actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
        }
    }

    void release(const SystemState& s,int op,int pid,int64_t required,std::vector<Action>& actions) {
        probability_cache_valid_=false;
        propose(s,op,pid,required,actions,R80_MODE==1?1:(R80_MODE==2?2:0));
        if(R80_MODE!=3 || required<=s.memory_limit-s.memory_used)return;
        for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)return;
        const int64_t now=s.hit_count+s.miss_count+1;
        if(uniform_cycle_ || (streak_>=6 && stride_>0 && observed_count_*2>now))return;
        pruneSpills(s,required,actions);
        std::vector<Action> alternative;propose(s,op,pid,required,alternative,2);
        pruneSpills(s,required,alternative);
        if(chooseAlternative(s,actions,alternative))actions.swap(alternative);
    }

    void pruneSpills(const SystemState& s, int64_t required, std::vector<Action>& a) {
        const int64_t need=required-(s.memory_limit-s.memory_used);
        int64_t freed=0;
        for (const auto& x:a) freed+=s.operators[x.op_id].partitions[x.partition_id].data_size;
        size_t keep=0;
        for (const auto& x:a) {
            const int64_t size=s.operators[x.op_id].partitions[x.partition_id].data_size;
            if (freed-size>=need) {freed-=size;continue;}
            a[keep++]=x;
        }
        a.erase(a.begin()+keep,a.end());
    }
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a); pruneSpills(s,z,a); record(s,a); return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        active_ = true; update(s,op,pid); std::vector<Action> a;
        release(s,op,pid,s.operators[op].partitions[pid].data_size,a);
        pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); record(s,a); return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        std::vector<Action> a;
        if (!active_) return a;
        update(s,-1,-1,true);
        if (s.next_op.type != "PROBE") return a;
        const int op=s.next_op.op_id;
        if (op < 0 || op >= static_cast<int>(s.operators.size())) return a;
        const int pid=static_cast<int>(s.next_op.key % p_);
        const auto& part=s.operators[op].partitions[pid];
        if (s.operators[op].phase != Phase::PROBE || part.in_memory ||
            part.data_size > s.memory_limit) return a;
        analyzeCycle(s);
        // Preserve the later miss callback's extra lookahead unless no eviction
        // is needed or the equal-size cyclic-route hypothesis supplies it.
        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) return a;
        release(s,op,pid,part.data_size,a); pruneSpills(s,s.operators[op].partitions[pid].data_size,a);
        a.emplace_back(Action::LOAD,op,pid); record(s,a); return a;
    }
// Appended public member methods; called only on a pre-callback deep copy.
public:
    void observerEmit(const SystemState& s,char tag,int op,int pid,int64_t required,
                      uint64_t callback,const std::vector<int>& thresholds,const std::vector<Action>& actual) const {
        static_assert(R80_MODE==2 && R74_SIZE==0,"observer is bound to exact R80 mode2 size0");
        obs11::require(tag=='M' || tag=='O',"unexpected observed callback");
        obs11::require(required>s.memory_limit-s.memory_used,"snapshot lacks release pressure");
        R80ObservedReference prepared(*this);
        prepared.active_=true;
        if(tag=='M')prepared.update(s,op,pid);else prepared.update(s);
        // Neither planner shares mutable vectors/caches with the actual scheduler or each other.
        R80ObservedReference hier(prepared),flat(prepared),view(prepared);
        std::vector<Action> ha,fa,actual_spills;
        hier.probability_cache_valid_=false;hier.propose(s,op,pid,required,ha,2);hier.pruneSpills(s,required,ha);
        flat.probability_cache_valid_=false;flat.propose(s,op,pid,required,fa,1);flat.pruneSpills(s,required,fa);
        for(const auto& a:actual)if(a.type==Action::SPILL)actual_spills.push_back(a);
        obs11::require(obs11::same(ha,actual_spills),"hier-copy spills differ from actual pruned spills");
        if(tag=='M')obs11::require(!actual.empty() && actual.back().type==Action::LOAD &&
            actual.back().op_id==op && actual.back().partition_id==pid,"actual demand LOAD missing");
        view.probability_cache_valid_=false;view.analyzeCycle(s);view.ensureProbabilities(s);
        const int n=static_cast<int>(view.next_mass_.size());
        for(int i=0;i<n;++i)view.ensureProbability(i);
        const int64_t now=s.hit_count+s.miss_count+1;
        const bool scan=view.streak_>=6 && view.stride_>0 && view.observed_count_*2>now;
        const bool cycle=view.uniform_cycle_;
        std::ostringstream out;out << std::setprecision(17);
        out << "OBS_STATE {\"callback\":" << callback << ",\"tag\":\"" << tag << "\",\"target_op\":" << op
            << ",\"target_partition\":" << pid << ",\"required_bytes\":" << required
            << ",\"q\":" << s.hit_count+s.miss_count << ",\"thresholds\":[";
        for(std::size_t j=0;j<thresholds.size();++j){if(j)out << ',';out << thresholds[j];}
        out << "],\"hier_copy_equals_actual_spills\":true,\"scan\":" << (scan?"true":"false")
            << ",\"cycle\":" << (cycle?"true":"false") << ",\"state\":";obs11::state(out,s);
        out << ",\"probability_clock\":" << view.probability_clock_ << ",\"next_sample_q\":" << view.next_sample_q_
            << ",\"total_mass\":";obs11::number(out,view.probability_total_);
        out << ",\"total_weight2\":";obs11::number(out,view.probability_weight2_);
        out << ",\"probability_prior_per_object\":";obs11::number(out,view.probability_prior_);
        out << ",\"probability_denom\":";obs11::number(out,view.probability_denom_);
        out << ",\"groups\":[";
        for(std::size_t o=0;o<view.sharing_.size();++o){if(o)out << ',';const auto& g=view.sharing_[o];
            out << "{\"op\":" << o << ",\"last\":" << g.last << ",\"mass\":";obs11::number(out,g.mass);
            out << ",\"squares\":";obs11::number(out,g.squares);out << ",\"weight2\":";obs11::number(out,g.weight2);
            out << ",\"share\":";obs11::number(out,g.share);out << ",\"heterogeneity\":";obs11::number(out,g.heterogeneity);
            out << ",\"n_eff\":";obs11::number(out,g.weight2>0?g.mass*g.mass/g.weight2:0.);out << '}';
        }
        out << "],\"objects\":[";
        for(int i=0;i<n;++i){if(i)out << ',';const int o=i/view.p_,pa=i%view.p_;
            const auto& part=s.operators[o].partitions[pa];const auto& c=view.next_mass_[i];
            const double mass=c.mass==0.?0.:c.mass*probabilityDecay(std::max<int64_t>(0,view.probability_clock_-c.last));
            const bool eligible=part.in_memory && part.data_size>0 && !(o==op && pa==pid);
            const bool protected_next=s.next_op.type=="PROBE" && s.next_op.op_id==o && s.next_op.key%view.p_==pa;
            const bool frequency=eligible && s.operators[o].phase==Phase::PROBE && !scan && !cycle;
            out << "{\"id\":" << i << ",\"op\":" << o << ",\"partition\":" << pa
                << ",\"size\":" << part.data_size << ",\"resident\":" << (part.in_memory?"true":"false")
                << ",\"eligible\":" << (eligible?"true":"false") << ",\"next_protected\":" << (protected_next?"true":"false")
                << ",\"frequency_branch\":" << (frequency?"true":"false") << ",\"mass\":";
            obs11::number(out,mass);out << ",\"flat_p\":";obs11::number(out,view.flat_probability_[i]);
            out << ",\"hier_p\":";obs11::number(out,view.hier_probability_[i]);out << '}';
        }
        out << "],\"actual_actions\":";obs11::actions(out,actual);
        out << ",\"hier_spills\":";obs11::actions(out,ha);out << ",\"flat_spills\":";obs11::actions(out,fa);
        out << ",\"cross_objectives\":{";
        auto objective=[&](const char* label,const std::vector<Action>& actions) {
            int64_t bytes=0;double ff=0,hh=0,protection=0;bool valid=!scan && !cycle;
            for(const auto& a:actions){const auto& part=s.operators[a.op_id].partitions[a.partition_id];
                const int id=a.op_id*view.p_+a.partition_id;bytes+=part.data_size;
                valid=valid && s.operators[a.op_id].phase==Phase::PROBE;
                const double cost=static_cast<double>(part.data_size)/s.read_bandwidth+
                    static_cast<double>(part.data_size)/s.write_bandwidth+100.;
                ff+=64.*view.flat_probability_[id]*cost;hh+=64.*view.hier_probability_[id]*cost;
                if(s.next_op.type=="PROBE" && s.next_op.op_id==a.op_id && s.next_op.key%view.p_==a.partition_id)
                    protection+=1e12*static_cast<double>(part.data_size);
            }
            const double write=static_cast<double>(bytes)/s.write_bandwidth;
            out << '"' << label << "\":{\"ordinary_frequency_objective_valid\":" << (valid?"true":"false")
                << ",\"victim_count\":" << actions.size() << ",\"spill_bytes\":" << bytes
                << ",\"released_excess_bytes\":" << bytes-(required-(s.memory_limit-s.memory_used))
                << ",\"actual_current_write_us\":";obs11::number(out,write);
            out << ",\"flat_future_proxy_us\":";obs11::number(out,ff);
            out << ",\"hier_future_proxy_us\":";obs11::number(out,hh);
            out << ",\"next_protection_term\":";obs11::number(out,protection);
            out << ",\"flat_subset_objective\":";obs11::number(out,ff+.25*write+protection);
            out << ",\"hier_subset_objective\":";obs11::number(out,hh+.25*write+protection);
            out << '}';
        };
        objective("hier_set",ha);out << ',';objective("flat_set",fa);out << "}}\n";
        std::cerr << out.str();
    }
};

// Only actual calls reach inner_; counterfactual calls use the pre-callback copy.
class MySpillScheduler : public SpillScheduler {
    R80ObservedReference inner_;
    uint64_t callback_=0;
    int next_threshold_=0,snapshots_=0;
    std::vector<Action> demand(const SystemState& s,char tag,int op,int pid,int64_t required) {
        ++callback_;const int bounds[3]={256,1024,4096};const int64_t q=s.hit_count+s.miss_count;
        const bool selected=next_threshold_<3 && q>=bounds[next_threshold_] && required>s.memory_limit-s.memory_used;
        std::vector<int> thresholds;std::unique_ptr<R80ObservedReference> before;
        if(selected) {
            while(next_threshold_<3 && q>=bounds[next_threshold_])thresholds.push_back(bounds[next_threshold_++]);
            before.reset(new R80ObservedReference(inner_));
        }
        auto actions=tag=='M'?inner_.onPartitionMiss(s,op,pid):inner_.onMemoryOverflow(s,op,pid,required);
        if(selected){before->observerEmit(s,tag,op,pid,required,callback_,thresholds,actions);++snapshots_;}
        return actions;
    }
public:
    ~MySpillScheduler() override {
        std::cerr << "OBS_END {\"callbacks\":" << callback_ << ",\"snapshots\":" << snapshots_
                  << ",\"thresholds_consumed\":" << next_threshold_ << "}\n";
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t bytes) override {
        return demand(s,'O',op,pid,bytes);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        return demand(s,'M',op,pid,s.operators[op].partitions[pid].data_size);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        ++callback_;return inner_.onPeriodicAdjust(s);
    }
};
