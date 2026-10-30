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

#pragma once
#include <limits>
#include <array>
#include <cmath>
// Frozen R65 observer methods copied verbatim except removal of unused BF member.
struct R66History {
 static const int C=512;
 struct Slot {std::int64_t size=-1,h=0,anchor=0,ghost=-1,reward=-1;};
 struct Intent {int op=0,pid=0;std::int64_t size=0,clock=0,h=0,anchor=0;bool reward=false;};
 Slot slots_[C];Intent spills_[C],load_;int count_=0;bool loading_=false,init_=false,supported_=false;
 std::size_t ops_=0;int parts_=0;std::int64_t clock_=0,limit_=0;Phase phases_[C];
 int id(int o,int p)const{return supported_&&o>=0&&p>=0&&static_cast<std::size_t>(o)<ops_&&p<parts_?o*parts_+p:-1;}
 static bool pos(const SystemState&s,int o,int p){return o>=0&&static_cast<std::size_t>(o)<s.operators.size()&&p>=0&&static_cast<std::size_t>(p)<s.operators[o].partitions.size();}
 static std::int64_t now(const SystemState&s){const auto m=std::numeric_limits<std::int64_t>::max();return s.hit_count<0||s.miss_count<0||s.hit_count>m-s.miss_count?-1:s.hit_count+s.miss_count;}
 void reset(const SystemState&s,std::int64_t t){ops_=s.operators.size();parts_=s.num_partitions;limit_=s.memory_limit;clock_=t;init_=true;count_=0;loading_=false;
  supported_=t>=0&&parts_>0&&ops_>0&&ops_<=C/static_cast<std::size_t>(parts_);
  for(std::size_t o=0;supported_&&o<ops_;++o)if(s.operators[o].op_id!=static_cast<int>(o)||s.operators[o].partitions.size()!=static_cast<std::size_t>(parts_))supported_=false;
  for(int i=0;i<C;++i)slots_[i]=Slot{};
  if(supported_)for(std::size_t o=0;o<ops_;++o)phases_[o]=s.operators[o].phase;
 }
 static void age(std::int64_t& h,std::int64_t& anchor,std::int64_t t){const auto d=(t-anchor)/64;if(d>=h){h=0;anchor=t;}else{h-=d;anchor+=d*64;}}
 Slot& touch(const SystemState&s,int o,int p){auto& x=slots_[id(o,p)];auto b=s.operators[o].partitions[p].data_size;if(x.size!=b){x=Slot{};x.size=b;x.anchor=clock_;}age(x.h,x.anchor,clock_);if(b>0)x.h=std::min(x.h,std::max<std::int64_t>(0,s.memory_limit/b));else x.h=0;return x;}
 void observe(const SystemState&s){auto t=now(s);bool invalid=!init_||ops_!=s.operators.size()||parts_!=s.num_partitions||t<clock_||limit_!=s.memory_limit;
  if(!invalid&&supported_)for(std::size_t o=0;o<ops_;++o){const auto& a=s.operators[o];if(a.op_id!=static_cast<int>(o)||a.partitions.size()!=static_cast<std::size_t>(parts_)||(phases_[o]==Phase::PROBE&&a.phase!=Phase::PROBE)){invalid=true;break;}}
  if(invalid){reset(s,t);return;}clock_=t;if(!supported_)return;
  for(std::size_t o=0;o<ops_;++o)phases_[o]=s.operators[o].phase;
  for(int i=0;i<count_;++i){auto a=spills_[i];auto& x=touch(s,a.op,a.pid);if(x.size==a.size&&!s.operators[a.op].partitions[a.pid].in_memory)x.ghost=a.clock;}count_=0;
  if(loading_){auto a=load_;auto& x=touch(s,a.op,a.pid);if(x.size==a.size&&s.operators[a.op].partitions[a.pid].in_memory){x.ghost=-1;if(a.reward&&x.reward!=a.clock){age(a.h,a.anchor,clock_);x.h=a.h;x.anchor=a.anchor;x.reward=a.clock;}}loading_=false;}
 }
 void record(const SystemState&s,const std::vector<Action>&as,int op,int pid,std::int64_t need,bool miss){count_=0;loading_=false;if(!supported_||as.size()>C||s.memory_used<0||s.memory_used>s.memory_limit)return;
  bool seen[C]{};auto used=s.memory_used;bool loaded=false;
  for(std::size_t i=0;i<as.size();++i){auto a=as[i];int k=id(a.op_id,a.partition_id);if(k<0||!pos(s,a.op_id,a.partition_id)||seen[k]){count_=0;loading_=false;return;}seen[k]=true;const auto&p=s.operators[a.op_id].partitions[a.partition_id];
   if(a.type==Action::SPILL){if(loaded||!p.in_memory||p.data_size<=0||p.data_size>used||(a.op_id==op&&a.partition_id==pid)){count_=0;loading_=false;return;}used-=p.data_size;if(s.operators[a.op_id].phase==Phase::PROBE){touch(s,a.op_id,a.partition_id);Intent v;v.op=a.op_id;v.pid=a.partition_id;v.size=p.data_size;v.clock=clock_;spills_[count_++]=v;}}
   else if(a.type==Action::LOAD){if(!miss||loaded||i+1!=as.size()||a.op_id!=op||a.partition_id!=pid||p.in_memory||p.data_size<0||p.data_size>s.memory_limit-used){count_=0;loading_=false;return;}loaded=true;used+=p.data_size;auto&x=touch(s,op,pid);load_=Intent{};load_.op=op;load_.pid=pid;load_.size=p.data_size;load_.clock=clock_;load_.h=x.h;load_.anchor=x.h?x.anchor:clock_;load_.reward=s.operators[op].phase==Phase::PROBE&&p.data_size>0&&x.ghost>=0&&clock_>=x.ghost&&clock_-x.ghost<=64&&x.reward!=clock_;if(load_.reward){auto cap=s.memory_limit/p.data_size;load_.h=x.h<cap?x.h+1:cap;}loading_=true;}
   else {count_=0;loading_=false;return;}
  }
  if((miss&&!loaded)||(!miss&&need>s.memory_limit-used)){count_=0;loading_=false;}
 }
};

namespace r66 {
struct Plan {std::vector<int> spill;std::array<float,16> x;double cost=0;std::int64_t bytes=0;};
inline int flat(const SystemState&s,int o,int p){return o*s.num_partitions+p;}
inline const PartitionState& part(const SystemState&s,int i){return s.operators[i/s.num_partitions].partitions[i%s.num_partitions];}
inline bool probe(const SystemState&s,int i){return s.operators[i/s.num_partitions].phase==Phase::PROBE;}
inline std::int64_t effective(const R66History&h,const SystemState&s,int i){
 const auto&x=h.slots_[i];auto b=part(s,i).data_size;if(x.size!=b||b<=0)return 0;
 auto heat=x.h,anchor=x.anchor;R66History::age(heat,anchor,h.clock_);return std::min(heat,s.memory_limit/b);
}
inline int nextTarget(const SystemState&s){const auto&n=s.next_op;return (n.type=="INSERT"||n.type=="PROBE")?flat(s,n.op_id,static_cast<int>(n.key%s.num_partitions)):-1;}
inline double victimCost(const SystemState&s,const R66History&h,int i){double b=part(s,i).data_size;return b/s.write_bandwidth+(probe(s,i)?b/s.read_bandwidth:0)+(s.next_op.type=="PROBE"&&nextTarget(s)==i?b/s.read_bandwidth:0)+static_cast<double>(effective(h,s,i))*b*(1/s.write_bandwidth+1/s.read_bandwidth);}
inline Plan makePlan(const SystemState&s,const R66History&h,std::vector<int>a,int target,std::int64_t need,bool miss){
 Plan p;p.spill=std::move(a);std::sort(p.spill.begin(),p.spill.end());double B=0,P=0,U=0,mx=0,resProbe=0;
 for(const auto&o:s.operators)for(const auto&v:o.partitions)if(v.in_memory&&o.phase==Phase::PROBE)resProbe+=v.data_size;
 bool nextVictim=false;int nt=nextTarget(s);
 for(int i:p.spill){double b=part(s,i).data_size;B+=b;P+=probe(s,i)?b:0;U+=static_cast<double>(effective(h,s,i))*b;mx=std::max(mx,b);p.cost+=victimCost(s,h,i);p.bytes+=part(s,i).data_size;if(i==nt)nextVictim=true;}
 double M=s.memory_limit,free=M-s.memory_used,d=std::max(0.,static_cast<double>(need)-free),T=M*(1/s.write_bandwidth+1/s.read_bandwidth),n=p.spill.size();
 p.x={{float(miss),float(free/M),float(need/M),float(d/M),float(resProbe/M),float(static_cast<double>(s.miss_count)/(static_cast<double>(s.hit_count)+s.miss_count+1)),float(B/M),float((B-d)/M),float(n/(n+1)),float(P/M),float(nextVictim&&s.next_op.type=="PROBE"),float(mx/M),float(U/(M+U)),float(p.cost/(T+p.cost)),float(s.write_bandwidth/(s.write_bandwidth+s.read_bandwidth)),float(nextVictim&&s.next_op.type=="INSERT")}};return p;
}
inline bool lessPlan(const Plan&a,const Plan&b){if(a.x[13]!=b.x[13])return a.x[13]<b.x[13];if(a.spill.size()!=b.spill.size())return a.spill.size()<b.spill.size();if(a.bytes!=b.bytes)return a.bytes<b.bytes;return a.spill<b.spill;}
inline bool tiePlan(const Plan&a,const Plan&b){if(a.spill.size()!=b.spill.size())return a.spill.size()<b.spill.size();if(a.bytes!=b.bytes)return a.bytes<b.bytes;return a.spill<b.spill;}
inline std::vector<Plan> pool(const SystemState&s,const R66History&h,int o,int pid,std::int64_t need,bool miss){
 int target=flat(s,o,pid);std::int64_t deficit=std::max<std::int64_t>(0,need-(s.memory_limit-s.memory_used));std::vector<Plan> out;
 auto add=[&](std::vector<int>a){std::sort(a.begin(),a.end());for(const auto&p:out)if(p.spill==a)return;out.push_back(makePlan(s,h,a,target,need,miss));};
 if(!deficit){add({});return out;}
 std::vector<int> eligible,singles;for(const auto&op:s.operators)for(const auto&p:op.partitions){int i=flat(s,op.op_id,p.partition_id);if(i!=target&&p.in_memory&&p.data_size>0){eligible.push_back(i);if(p.data_size>=deficit)singles.push_back(i);}}
 std::sort(singles.begin(),singles.end(),[&](int a,int b){double ca=victimCost(s,h,a),cb=victimCost(s,h,b);if(ca!=cb)return ca<cb;auto za=part(s,a).data_size,zb=part(s,b).data_size;return za!=zb?za<zb:a<b;});
 for(std::size_t i=0;i<std::min<std::size_t>(4,singles.size());++i)add({singles[i]});
 if(!singles.empty()){
 int small=singles[0],large=small;for(int i:singles){auto b=part(s,i).data_size;if(b<part(s,small).data_size||(b==part(s,small).data_size&&i<small))small=i;if(b>part(s,large).data_size||(b==part(s,large).data_size&&i<large))large=i;}add({small});add({large});}
 for(int mode=0;mode<2;++mode){auto avail=eligible;std::vector<int>a;auto left=deficit;while(left>0&&!avail.empty()){
 int pick=-1;if(mode==0)for(int i:avail)if(part(s,i).data_size>=left&&(pick<0||part(s,i).data_size<part(s,pick).data_size||(part(s,i).data_size==part(s,pick).data_size&&i<pick)))pick=i;
 if(pick<0)for(int i:avail)if(pick<0||part(s,i).data_size>part(s,pick).data_size||(part(s,i).data_size==part(s,pick).data_size&&i<pick))pick=i;
 a.push_back(pick);left-=part(s,pick).data_size;avail.erase(std::find(avail.begin(),avail.end(),pick));}if(left<=0)add(a);}
 return out;
}
inline std::vector<Action> emit(const SystemState&s,const Plan&p,int o,int pid,bool miss){std::vector<Action>a;for(int i:p.spill)a.emplace_back(Action::SPILL,i/s.num_partitions,i%s.num_partitions);if(miss)a.emplace_back(Action::LOAD,o,pid);return a;}
}
// score hook has signature float(const std::array<float,16>&). All work stays in callbacks.
template<class Score> class R66Scheduler:public SpillScheduler {
 R66History h;Score score;
 std::vector<Action> choose(const SystemState&s,int o,int p,std::int64_t need,bool miss){h.observe(s);auto plans=r66::pool(s,h,o,p,need,miss);assert(!plans.empty());std::size_t best=0;
 for(std::size_t i=1;i<plans.size();++i){auto a=score(plans[i].x),b=score(plans[best].x);if(a<b||(a==b&&r66::tiePlan(plans[i],plans[best])))best=i;}
 auto a=r66::emit(s,plans[best],o,p,miss);h.record(s,a,o,p,need,miss);return a;}
 public:std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return choose(s,o,p,n,false);}std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}std::vector<Action>onPeriodicAdjust(const SystemState&s)override{h.observe(s);return {};}
};
struct R66BaseScore {float operator()(const std::array<float,16>&x)const{return x[13];}};

class MySpillScheduler:public R66Scheduler<R66BaseScore>{};


class NaiveSpillScheduler: public SpillScheduler {
  MySpillScheduler inner;
  std::vector<Action> step(const SystemState&s,char tag,int o,int p,std::int64_t n){
    std::vector<Action>a;
    if(tag=='O') a=inner.onMemoryOverflow(s,o,p,n);
    else if(tag=='M') a=inner.onPartitionMiss(s,o,p);
    else a=inner.onPeriodicAdjust(s);
    std::cerr<<"R66TRACE "<<tag<<' '<<o<<' '<<p<<' '<<n<<' '
      <<s.memory_used<<' '<<s.hit_count<<' '<<s.miss_count<<' '<<s.total_io_bytes<<' '
      <<(s.next_op.type.empty()?"-":s.next_op.type)<<' '<<s.next_op.op_id<<' '
      <<s.next_op.key<<' '<<s.next_op.tuple_size;
    for(const auto&op:s.operators){std::cerr<<' '<<(op.phase==Phase::PROBE?1:0);
      for(const auto&v:op.partitions)std::cerr<<' '<<v.data_size<<' '<<(v.in_memory?1:0);}
    std::cerr<<' '<<a.size();for(const auto&v:a)std::cerr<<' '
      <<(v.type==Action::SPILL?'S':'L')<<' '<<v.op_id<<' '<<v.partition_id;
    std::cerr<<'\n';return a;
  }
public:
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return step(s,'O',o,p,n);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return step(s,'M',o,p,s.operators[o].partitions[p].data_size);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{return step(s,'P',-1,-1,0);}
};
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

    auto scheduler = std::make_unique<NaiveSpillScheduler>();
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
