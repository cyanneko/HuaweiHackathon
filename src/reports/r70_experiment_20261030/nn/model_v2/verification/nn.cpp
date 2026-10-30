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

#pragma once
#include <cmath>
#include <limits>
inline float r70_score(const float x[32]) {
 static const float w1[16][32]={{0.0867126808f, 0.110532105f, 0.0450300314f, -0.0664922819f, 0.0661219656f, 0.0834639072f, 0.00332102645f, -0.0925599337f, 0.0317715667f, -0.114891797f, 0.314522445f, -0.0866391063f, -0.0572759137f, -0.135464594f, 0.0574379936f, -0.155172437f, -0.0962973163f, 0.0138230547f, -0.0832844973f, -0.171699122f, 0.0192199014f, 0.0180071909f, -0.0275908187f, -0.0922251269f, -0.0349859484f, -0.0741146654f, -0.125606135f, -0.0302726943f, 0.16003792f, 0.0624716058f, 0.0400572605f, -0.109721974f},
{-0.071939148f, 0.172147647f, -0.0610062927f, -0.127383232f, -0.0669666454f, -0.0902956501f, -0.134012908f, 0.0342474058f, 0.100370303f, -0.185781702f, 0.126053527f, -0.153144881f, -0.156678602f, -0.0580037124f, 0.0439934954f, -0.275637448f, -0.0341966264f, -0.036517933f, -0.220786273f, -0.171737909f, -0.0429108813f, -0.0467070378f, 0.025990393f, -0.0631555617f, -0.0516975969f, -0.091852814f, -0.126069084f, 0.113806218f, 0.0770140439f, 0.0754817575f, -0.0363366641f, -0.143524766f},
{-0.0907162577f, 0.235671908f, -0.0602504835f, -0.0827038363f, 0.0409166664f, 0.081979394f, -0.106963947f, -0.0589348674f, 0.0204406418f, -0.0226342492f, 0.340915173f, -0.0641142875f, -0.0832860842f, -0.0643334389f, 0.088785477f, -0.307303756f, 0.081639573f, 0.015693482f, -0.0818664208f, -0.217557281f, -0.134061143f, -0.066671811f, 0.0403522141f, 0.0451943502f, -0.102887668f, -0.173279643f, -0.0767589137f, -0.0194073804f, 0.140687451f, 0.212487012f, -0.08841075f, 0.0333767906f},
{-0.0338409282f, 0.203765795f, 0.0226453021f, 0.0950229913f, 0.11463473f, 0.132079288f, -0.0603626631f, -0.0856072083f, 0.031542819f, -0.0472833589f, 0.196203262f, 0.0495401286f, -0.212211132f, 0.0202334095f, 0.138978094f, -0.295319527f, -0.0294962712f, -0.0420894399f, -0.0608027503f, -0.0255358443f, -0.0506232269f, -0.147753537f, 0.0204994343f, -0.0236517731f, -0.0482611582f, -0.0254861452f, -0.214281052f, -0.0128567256f, 0.0683720708f, 0.218219116f, -0.131781757f, -0.0504465662f},
{0.0814176276f, -0.26143387f, 0.172934458f, 0.189051464f, 0.0268876553f, 0.0803039223f, 0.196838915f, 0.192214176f, -0.000654110627f, 0.178906336f, -0.202275649f, 0.181285933f, 0.23774837f, 0.162324205f, 0.100886621f, 0.296349794f, 0.28734082f, 0.247769177f, 0.218161955f, 0.285667121f, 0.107357837f, 0.0936653614f, 0.0388979539f, -0.0106375953f, 0.114677832f, 0.107756995f, 0.169792026f, -0.0167846698f, -0.00335541274f, -0.132894158f, 0.197643429f, -0.00484468415f},
{0.133364201f, 0.262481958f, 0.0568473339f, -0.117176868f, 0.00607983954f, 0.0375990197f, -0.0338386633f, -0.131223366f, 0.106918707f, -0.0651950389f, 0.326718092f, -0.115106292f, -0.14053832f, 0.00963140372f, 0.162930086f, -0.292959303f, -0.120570138f, -0.122906834f, -0.129169226f, -0.223677397f, 0.00851741061f, -0.000326859241f, -0.0379514769f, 0.0328851454f, 0.0420438908f, 0.072674118f, -0.102269471f, 0.0407301635f, 0.091724351f, 0.253423035f, -0.111022629f, 0.0759176314f},
{0.0755054057f, 0.206268519f, 0.0698082522f, -0.0631520525f, 0.0306330938f, 0.000331741758f, -0.134937331f, -0.160236955f, 0.102288648f, -0.078350693f, 0.222523749f, -0.0849287957f, -0.051270999f, -0.0117901741f, -0.0572943352f, -0.218979657f, -0.00342685822f, -0.160714552f, -0.203410879f, -0.056939479f, -0.0776197091f, -0.0230262205f, 0.00809849426f, -0.120137326f, 0.0797585919f, -0.0574476719f, -0.0425866395f, 0.168527707f, 0.0791576952f, 0.0632884875f, -0.0638503209f, -0.0574491881f},
{-0.08556889f, -0.174492776f, -0.188524693f, -0.152765945f, -0.138245404f, 0.200378075f, -0.189038277f, -0.131488875f, 0.139901802f, -0.12023735f, 0.116603717f, -0.0793489739f, 0.119360507f, 0.0226496235f, 0.0501864366f, -0.27500695f, -0.165599704f, -0.0965357795f, -0.10060703f, -0.206880003f, 0.187083483f, 0.148861468f, 0.1716519f, 0.0196303669f, -0.14505969f, 0.144132778f, 0.0967178792f, 0.0762507394f, 0.00288342382f, 0.0654649809f, -0.0395130366f, 0.0162921175f},
{-0.0448520742f, 0.269206554f, -0.00433466583f, -0.230689302f, -0.103043199f, 0.0238182675f, -0.126684234f, 0.0443906561f, 0.0267672278f, -0.0600785874f, 0.347969502f, -0.0466105118f, -0.0934653655f, -0.0299146865f, -0.074267894f, -0.215483576f, -0.0257545095f, 0.0399277881f, -0.116069295f, -0.0613014512f, 0.0291951187f, 0.0146430898f, 0.10407304f, 0.0762609765f, -0.0348305069f, -0.0678068921f, -0.119955994f, 0.0961060524f, 0.266979486f, 0.0847352967f, 0.0715323612f, -0.161521301f},
{-0.0846598595f, -0.0285839327f, -0.169749737f, -0.102957323f, -0.00635717995f, -0.0431729555f, -0.167049751f, -0.100384377f, -0.0161853526f, -0.0963198692f, 0.122648992f, -0.16681692f, -0.166549146f, -0.0559143908f, 0.0631403774f, -0.185084075f, -0.065047279f, 0.00213265582f, -0.185948014f, -0.136235043f, -0.127750516f, -0.0584801659f, -0.167782322f, -0.0763449669f, 0.0734355152f, -0.169994667f, -0.0261657182f, -0.0241017789f, 0.0760460645f, 0.0591093004f, 0.0264416393f, -0.14621897f},
{0.00301920623f, 0.175017178f, -0.027321903f, -0.0339305997f, 0.0883617029f, 0.044833906f, -0.0280108843f, -0.0862701014f, -0.0298512354f, -0.0216390658f, 0.247356579f, -0.0528126322f, -0.0450127572f, -0.104735501f, 0.0814185664f, -0.282130361f, -0.0157083478f, -0.0713179111f, -0.0186166503f, -0.102679588f, 0.013344055f, -0.148779437f, -0.00743091386f, -0.0121941352f, 0.0342915803f, -0.07938198f, -0.183014333f, 0.0240647979f, 0.195052698f, 0.122880235f, 0.0362101533f, 0.0246792994f},
{-0.0341819301f, 0.213371485f, 0.0293121561f, -0.0773541704f, -0.000490087783f, -0.0288327448f, 0.0448219068f, 0.0366092287f, 0.0633251294f, -0.0730127543f, 0.352991045f, -0.0655318722f, -0.124460667f, -0.0311010443f, 0.114707477f, -0.200489521f, -0.0251412466f, -0.0505687743f, 0.173401773f, -0.0655293316f, -0.0953837782f, 0.026951218f, -0.123721935f, -0.0130083775f, -0.0329787545f, 0.01165694f, -0.212584242f, 0.00164767145f, 0.216828406f, 0.230909035f, -0.0765196532f, -0.0178735591f},
{0.0387159735f, 0.234848782f, 0.068706207f, -0.0939559266f, 0.11485368f, 0.149351433f, -0.0821218044f, -0.0311129279f, 0.112323344f, -0.0293940268f, 0.287239909f, -0.0270553585f, -0.278229475f, -0.02444553f, 0.0323716216f, -0.204061657f, -0.088358894f, -0.0880095437f, -0.160480708f, -0.136088222f, -0.00968306977f, -0.166485399f, -0.135354564f, -0.0818433315f, 0.100956164f, -0.118046306f, -0.115910113f, 0.105164237f, 0.212414443f, 0.141602516f, 0.0370609462f, 0.0154989026f},
{0.0779794529f, 0.16947557f, 0.00184469717f, -0.0511399359f, -0.0518866368f, 0.0192328077f, -0.0432317853f, -0.0333125666f, 0.0408482961f, 0.0474968664f, 0.171029136f, -0.0829710513f, -0.140118241f, -0.101331599f, 0.0461583696f, -0.288600206f, -0.104640998f, 0.0540460348f, -0.121819794f, -0.1914161f, -0.208937332f, -0.143538073f, -0.18904005f, -0.177051082f, 0.0237936396f, -0.0689692348f, -0.0643707812f, 0.0204471778f, 0.149627373f, 0.192783073f, -0.0478705317f, 0.0561046787f},
{-0.0375323892f, 0.24230592f, 0.0953053907f, -0.11322777f, 0.0355019681f, 0.16402331f, -0.0151605308f, -0.00969468709f, 0.0250823759f, -0.132144094f, 0.337881267f, -0.10399127f, -0.0364400297f, -0.054419525f, 0.0945981517f, -0.274809301f, 0.0719744861f, -0.0890252218f, -0.0889541581f, -0.155300304f, -0.00557914656f, -0.0485164598f, -0.0913976431f, 0.0282697324f, 0.111689992f, -0.101128154f, -0.1048951f, 0.103495665f, 0.0858722478f, 0.212426484f, 0.00935733132f, -0.0698582307f},
{0.109062143f, 0.166021138f, -0.0119940843f, 0.00743998541f, 0.0581544153f, 0.171092749f, -0.103469841f, -0.121515445f, 0.063255541f, -0.135509521f, 0.319656372f, -0.153690264f, -0.191429272f, -0.0632211939f, 0.0276848972f, -0.192082703f, -0.112591572f, -0.0414388031f, 0.0106337219f, -0.0768863484f, 0.0433297418f, -0.066867806f, -0.134745806f, -0.0627144575f, -0.035681311f, 0.0244234018f, -0.14648895f, 0.1211145f, 0.245035008f, 0.200909689f, 0.0807052031f, -0.0727983788f}};
 static const float b1[16]={0.0990820229f, 0.0577826649f, 0.0829719678f, 0.101718783f, 0.120395288f, 0.119472913f, 0.0914826989f, 0.116759382f, 0.0602482334f, 0.0687061325f, 0.104789756f, 0.0976899341f, 0.101818502f, 0.0897767022f, 0.112094432f, 0.113395929f};
 static const float w2[16]={0.0228327345f, 0.0124209682f, 0.0884120539f, 0.0661291331f, -0.134118617f, 0.10529425f, 0.00473333709f, 0.175210074f, 0.0726280063f, -0.015256918f, 0.0528491251f, 0.111517243f, 0.0878499746f, 0.0860646069f, 0.0776555091f, 0.109579243f};
 float z=0.108503155f;
 for(int i=0;i<32;++i)if(!std::isfinite(x[i]))return std::numeric_limits<float>::infinity();
 for(int j=0;j<16;++j){float h=b1[j];for(int i=0;i<32;++i)h+=w1[j][i]*x[i];z+=w2[j]*(h>0?h:0);}
 z=x[13]+(z<-1?-1:(z>1?1:z));return std::isfinite(z)?z:std::numeric_limits<float>::infinity();
}

#pragma once
#include <array>
#include <cmath>


// Framework types precede this header. Same causal observer and <=8 legal plans.
namespace r70 {
inline std::vector<int> r65Choice(const SystemState&s,const R66History&h,int target,std::int64_t need){
 auto left=std::max<std::int64_t>(0,need-(s.memory_limit-s.memory_used));std::vector<int>a,avail;
 if(!left)return a;int single=-1;
 for(const auto&o:s.operators)for(const auto&p:o.partitions){int i=r66::flat(s,o.op_id,p.partition_id);if(i==target||!p.in_memory||p.data_size<=0)continue;avail.push_back(i);
  if(p.data_size>=left){if(single<0)single=i;else {double x=r66::victimCost(s,h,i),y=r66::victimCost(s,h,single);auto b=r66::part(s,single).data_size;if(x<y||(x==y&&(p.data_size<b||(p.data_size==b&&i<single))))single=i;}}}
 if(single>=0)return {single};
 while(left>0&&!avail.empty()){int pick=-1;
  for(int i:avail)if(r66::part(s,i).data_size>=left&&(pick<0||r66::part(s,i).data_size<r66::part(s,pick).data_size||(r66::part(s,i).data_size==r66::part(s,pick).data_size&&i<pick)))pick=i;
  if(pick<0)for(int i:avail)if(pick<0||r66::part(s,i).data_size>r66::part(s,pick).data_size||(r66::part(s,i).data_size==r66::part(s,pick).data_size&&i<pick))pick=i;
  a.push_back(pick);left-=r66::part(s,pick).data_size;avail.erase(std::find(avail.begin(),avail.end(),pick));}
 std::sort(a.begin(),a.end());return a;
}
inline std::vector<std::array<float,32>> features(const SystemState&s,const R66History&h,const std::vector<r66::Plan>&ps,int target,std::int64_t need){
 std::vector<std::array<float,32>> out(ps.size());auto chosen=r65Choice(s,h,target,need);
 const auto&next=s.next_op;int owner=(next.type=="INSERT"||next.type=="PROBE"||next.type=="SWITCH")?next.op_id:-1;
 double M=s.memory_limit;
 for(std::size_t j=0;j<ps.size();++j){const auto&p=ps[j];auto&x=out[j];std::copy(p.x.begin(),p.x.end(),x.begin());
  double n=p.spill.size(),sum=0,mn=1e100,sq=0,hs=0,hx=0,hw=0,hot=0,probe=0,recent=0,recency=0,sameop=0;
  for(int i:p.spill){double b=static_cast<double>(r66::part(s,i).data_size)/M,heat=r66::effective(h,s,i);sum+=b;mn=std::min(mn,b);sq+=b*b;hs+=heat;hx=std::max(hx,heat);hw+=heat*static_cast<double>(r66::part(s,i).data_size);hot+=heat>0;probe+=r66::probe(s,i);sameop+=i/s.num_partitions==owner;
   const auto&slot=h.slots_[i];auto age=h.clock_-slot.reward;if(slot.size==r66::part(s,i).data_size&&slot.reward>=0&&age>=0&&age<=64){recent+=1;recency+=(65.-age)/65.;}}
  double mean=n?sum/n:0,var=0;for(int i:p.spill){double d=static_cast<double>(r66::part(s,i).data_size)/M-mean;var+=d*d;}double hm=n?hs/n:0,wh=p.bytes?hw/p.bytes:0;
  x[16]=n?mn:0;x[17]=mean;x[18]=n?std::sqrt(var/n):0;x[19]=sq;x[20]=hx/(1+hx);x[21]=hm/(1+hm);x[22]=wh/(1+wh);x[23]=n?hot/n:0;x[24]=n?probe/n:0;x[25]=n?recent/n:0;x[26]=n?recency/n:0;x[27]=n?sameop/n:0;
  double cr=0,wr=0,dr=0,d=p.bytes?p.cost/p.bytes:0;
  for(const auto&q:ps){cr+=q.cost<p.cost;wr+=q.bytes<p.bytes;dr+=(q.bytes?q.cost/q.bytes:0)<d;}
  double denom=std::max<std::size_t>(1,ps.size()-1);x[28]=cr/denom;x[29]=wr/denom;x[30]=dr/denom;x[31]=p.spill==chosen;
 }return out;
}
}

#include <cstring>
inline void r70detail(const R66History&h,const std::vector<r66::Plan>&ps,const std::vector<std::array<float,32>>&xs){
 std::uint64_t xh=14695981039346656037ULL,hh=xh;
 auto mix=[](std::uint64_t&z,std::uint64_t v){z^=v;z*=1099511628211ULL;};
 mix(xh,ps.size());for(std::size_t j=0;j<ps.size();++j){mix(xh,ps[j].spill.size());for(int i:ps[j].spill)mix(xh,i);for(float f:xs[j]){std::uint32_t b;std::memcpy(&b,&f,4);mix(xh,b);}float z=r70_score(xs[j].data());std::uint32_t b;std::memcpy(&b,&z,4);mix(xh,b);}
 mix(hh,h.clock_);for(std::size_t i=0;i<h.ops_*h.parts_;++i){const auto&v=h.slots_[i];mix(hh,v.size);mix(hh,v.h);mix(hh,v.anchor);mix(hh,v.ghost);mix(hh,v.reward);}
 std::cerr<<"R70DETAIL "<<xh<<' '<<hh<<'\n';
}

class MySpillScheduler:public SpillScheduler {
 R66History history_;
 std::vector<Action> choose(const SystemState&s,int o,int pid,std::int64_t need,bool miss){
  history_.observe(s);auto plans=r66::pool(s,history_,o,pid,need,miss);assert(!plans.empty());
  if(plans.size()==1){auto a=r66::emit(s,plans[0],o,pid,miss);history_.record(s,a,o,pid,need,miss);return a;}
  auto xs=r70::features(s,history_,plans,r66::flat(s,o,pid),need);r70detail(history_,plans,xs);std::size_t best=0;
  float bestScore=r70_score(xs[0].data());
  for(std::size_t j=1;j<plans.size();++j){float score=r70_score(xs[j].data());if(score<bestScore||(score==bestScore&&r66::tiePlan(plans[j],plans[best]))){best=j;bestScore=score;}}
  auto a=r66::emit(s,plans[best],o,pid,miss);history_.record(s,a,o,pid,need,miss);return a;
 }
 public:
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{history_.observe(s);return {};}
};


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
