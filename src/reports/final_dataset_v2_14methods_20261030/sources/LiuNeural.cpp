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

// Single-file C++14 scheduler. Uses only SystemState, next_op and own history.
// Flags are for reproducible local ablations; the evaluator uses no arguments.
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>
#include <cmath>

class MySpillScheduler final : public SpillScheduler {
    // Inference sees only public state and scheduler-owned observations.
    int policy_mode_=-1,forced_next_=-1,selected_expert_=7;
    std::array<double,512> gds_{};double gds_clock_=0;
    uint64_t choices_=0,inferences_=0;
    static double bounded(double x){return std::max(0.0,std::min(1.0,x));}
        static int network(const std::array<float,32>& x) {
        static const float w1[16][32]={{-0.342048049f,0.155758038f,-0.081467621f,-0.0504218154f,0.378917694f,-0.0472420417f,-0.115290917f,0.167673662f,0.271011561f,0.138152912f,-0.126474455f,-0.0163992289f,-0.0284270011f,-0.110187106f,0.189731702f,0.155369163f,-0.481442779f,0.28298974f,-0.190290496f,0.11739891f,-0.0854192004f,-0.0973568112f,-0.00139165646f,-0.0716098621f,-0.173554018f,-0.0352752171f,-0.479713768f,-0.00056380732f,-0.232093632f,-0.211647451f,-0.0354464501f,-0.115613781f},{0.177782238f,0.023292724f,-0.492488533f,-0.143297136f,-0.311589718f,-0.726004899f,0.151373193f,-0.0577943511f,-0.392090023f,0.203027144f,-0.604783535f,0.283831537f,-0.296852618f,-0.548496544f,0.402286321f,0.322340965f,-0.909635067f,-0.215008393f,-0.0359557047f,-0.406816095f,0.313308537f,-0.261735409f,0.315200806f,-0.0441820957f,0.0300704446f,-0.221069857f,-0.659545898f,0.123104118f,0.23464027f,-0.101043753f,0.113889173f,-0.455687702f},{-0.220462605f,-0.673124015f,-0.428058118f,-0.406576216f,0.191355363f,0.151273221f,0.0452418886f,-0.0750177428f,0.0541602224f,0.0546162464f,-0.236263394f,-0.567891717f,0.244090542f,-0.162619174f,0.477383405f,-0.6365242f,0.00798125193f,0.0784292147f,0.320632637f,0.181497991f,-0.0926610157f,0.0292337276f,0.0481886677f,0.193368331f,-0.122758277f,-0.654934466f,-0.273584366f,-0.145046666f,0.339877248f,0.0156061929f,0.00233005616f,-0.338287771f},{-0.182801887f,-0.0256816279f,0.019256575f,-0.0676700175f,0.00349352276f,0.364933312f,-0.420764714f,-0.00321459537f,0.67222923f,0.193917975f,-0.337182671f,0.0942048505f,0.379464656f,-0.124160551f,0.117644228f,0.273838639f,-0.288926929f,0.183595508f,-0.31000194f,-0.344775051f,0.0371060036f,-0.289191484f,-0.231269613f,0.233531967f,0.0720216557f,-0.100424305f,-0.282764375f,0.0701768771f,-0.0612978563f,-0.00101769995f,-0.0504289195f,-0.114806555f},{0.269620806f,-0.0952547118f,-0.111457981f,-0.117200814f,-0.238072723f,-0.686251819f,0.361384749f,-0.22347337f,0.12294025f,-0.392960548f,-0.257946521f,0.259595752f,-0.469839215f,0.0980333984f,0.250050634f,0.0802159831f,-0.473729432f,0.0496647693f,0.0689543486f,0.00504000671f,-0.298505872f,0.0364904068f,0.0158105325f,-0.0935311094f,0.271080375f,0.326152086f,0.0126449093f,0.01353072f,0.175130382f,-0.436011404f,-0.0305776559f,-0.166407287f},{-0.0589059889f,-0.102941759f,-0.0555604175f,-0.426079839f,-0.146527708f,0.190207332f,0.158521757f,-0.119510584f,-0.757205427f,-0.00828819256f,-0.372099668f,0.406671554f,-0.406431705f,0.0592934974f,0.123761125f,0.092769295f,-0.745635331f,0.225426614f,0.0400064401f,-0.0153638646f,0.43795678f,-0.00200939411f,0.191720158f,0.106806159f,-0.0792707205f,-0.306146175f,-0.391923189f,-0.371641129f,-0.306468695f,-0.427266002f,0.163404599f,-0.618720353f},{-0.0614488125f,-0.176456764f,-0.246641964f,-0.675444901f,0.0650653318f,-0.375886202f,-0.144089773f,-0.150892347f,0.83968997f,0.297674596f,-0.523782969f,0.41211912f,-0.453110039f,-0.291100025f,0.0227180663f,0.360827655f,-0.989770055f,0.134640932f,-0.575300217f,0.31722948f,-0.0259761307f,-0.0798064619f,-0.102443226f,-0.0315917023f,0.11521516f,0.47591877f,-0.275059462f,-0.00778105296f,-0.303207725f,-0.794852316f,-0.0922758132f,-0.00140093337f},{0.124918506f,-0.29432252f,-0.587292433f,-0.0949479118f,-0.0373116061f,-0.205578133f,0.215685129f,-0.109717071f,0.0657038018f,0.0454544574f,-0.24315998f,-0.100322619f,-0.241244987f,-0.348459959f,0.305224597f,-0.147767439f,-0.232185021f,-0.145530134f,0.418120563f,0.290687859f,0.374741465f,-0.0910664871f,0.377901763f,0.281079292f,0.0814633071f,-0.589324415f,-0.433627188f,-0.0495392419f,0.0515644439f,-0.0798540711f,-0.102603719f,-0.439388543f},{-0.215761736f,0.0135830948f,0.386404872f,-0.363874912f,-0.0167800002f,0.349247605f,0.000861443812f,-0.301314712f,0.62588495f,0.277037799f,0.128572807f,-0.448938191f,0.388003141f,-0.155750886f,0.200997636f,-0.310677081f,-0.182540283f,-0.253710002f,0.0919393972f,-0.256104976f,0.10123039f,-0.0385992974f,0.120619863f,0.0696037412f,0.0820681155f,-0.716314733f,-0.651350379f,0.164186791f,-0.795329571f,-0.144866109f,0.147606373f,-0.189313084f},{0.0679260194f,-0.13437587f,0.240695372f,-0.487206161f,-0.471049339f,-0.034041021f,-0.232620582f,0.0173716806f,0.00668032188f,-0.521030903f,-0.182259589f,-0.601858258f,-0.710817695f,-0.0286131147f,0.0925857797f,0.217410743f,-0.00101459189f,0.199572727f,-0.186163828f,0.295436502f,0.0957712606f,0.158294469f,-0.0280146003f,-0.779696643f,0.446716756f,-0.495815665f,0.0722172186f,0.210437626f,-0.397749603f,0.172295019f,0.0244005118f,-0.45467031f},{-0.0362904742f,0.161631718f,0.0827566311f,-0.0686216131f,0.0912554413f,0.199316621f,-0.0956320241f,0.112236634f,0.228849724f,-0.00505858194f,-0.163462371f,-0.056676209f,-0.160601288f,-0.269116074f,-0.0885041505f,0.0479034744f,-0.503378153f,0.101617314f,0.117121197f,-0.100024037f,0.0997624248f,0.225789368f,0.248836294f,0.230149195f,-0.352176189f,-0.165825859f,-0.388356924f,0.126468286f,-0.562919021f,-0.0915718526f,-0.235885084f,-0.181179896f},{-0.0155026475f,-0.363361448f,-0.360838413f,-0.501383483f,-0.077942349f,-0.190919787f,-0.375187457f,0.150036126f,0.472911298f,0.416807234f,-0.338699669f,0.0804699734f,-0.405896872f,-0.362348974f,-0.107783698f,0.515295744f,-1.00584567f,0.0173629858f,-0.271231294f,-0.15663752f,0.125745758f,0.078796342f,-0.203150868f,0.0742418095f,0.0313937701f,-0.653645456f,-1.22824025f,-0.20720388f,-0.251882225f,-0.491537809f,0.131191343f,-0.380945146f},{-5.25836585e-05f,9.03997126e-26f,9.72215057e-24f,-6.30603395e-31f,2.04731464e-07f,4.45917455e-19f,-1.35349467e-06f,-1.30850192e-11f,-4.63087616e-07f,-3.90573901e-12f,-1.69419589e-27f,3.95066269e-19f,-1.08056255e-11f,5.85238649e-06f,-5.7909398e-15f,-5.39477574e-09f,-1.76561954e-26f,-1.58042926e-10f,-6.2716839e-07f,2.53167738e-20f,7.37503456e-07f,0.000152785768f,-3.44476484e-06f,-1.17892787e-24f,-8.07191292e-09f,-2.222212e-29f,-9.97285622e-28f,-2.75502067e-20f,2.49440636e-18f,2.93970185e-30f,-7.74088403e-05f,6.03425114e-18f},{-0.0815458745f,-0.154980913f,0.0278001092f,-0.403663069f,-0.078799583f,0.313851446f,-0.110064849f,-0.0302204341f,0.571492732f,0.196373954f,-0.19553487f,-0.0772533268f,-0.473000467f,-0.163597271f,-0.00883760862f,-0.0767407194f,-0.774342835f,-0.0611016266f,-0.497754574f,0.352995336f,0.110506624f,0.107229151f,-0.0996046215f,0.279530704f,0.370644867f,-0.700315773f,-1.06743097f,-0.406966984f,-0.735091209f,-0.421007246f,-0.0841667503f,-0.244618401f},{-0.136202052f,-0.176093787f,-0.438038677f,-0.183736145f,0.0297633391f,-0.228800341f,0.173521072f,-0.113781512f,0.403671682f,0.59086597f,-0.728696704f,-0.121724077f,0.287181735f,0.0260328874f,0.303910404f,0.230452374f,-0.801177561f,0.166665569f,-0.174910933f,-0.471168369f,-0.11590559f,-0.00960741192f,0.00938542746f,-0.649826646f,-0.333613843f,0.0996036083f,-0.367576092f,0.258802742f,-0.103510655f,0.0978310257f,-0.179553956f,-0.384380043f},{-0.0222249832f,-0.222316608f,-0.18377766f,-0.260197192f,-0.0573961586f,-0.260892987f,-0.377854973f,0.194039106f,0.116005301f,-0.430002213f,-0.0143270642f,-0.0940475836f,-0.304278225f,-0.195425287f,0.0880936757f,0.0832996219f,0.00448280293f,-0.387798131f,0.407819539f,-0.237713546f,0.226207048f,0.00619165134f,-0.105835415f,0.0281349644f,0.184890807f,-0.533070862f,-0.288225412f,0.0750028715f,0.634291589f,-0.166689232f,0.000602239394f,-0.336159676f}};
        static const float b1[16]={-0.0840582028f,0.034861654f,0.0356160067f,-0.0963638648f,0.108485363f,0.121103123f,-0.0666693226f,-0.123223186f,-0.0195563361f,-0.0805757716f,-0.0313385092f,-0.182372928f,-0.0572706722f,-0.0841376707f,-0.0457987338f,-0.139376462f};
        static const float w2[8][16]={{0.0152186649f,-0.663402677f,0.261982441f,0.00834307447f,-0.244447142f,-0.251271933f,-0.709362924f,-0.138374761f,0.328525543f,-0.0149087403f,-0.112183586f,-0.613332391f,-0.000161956705f,-0.408732951f,-0.344601214f,-0.313608468f},{0.117800876f,0.340550542f,-0.457072347f,0.222785875f,0.692097723f,0.755170465f,0.448425353f,-0.111876287f,-0.381349742f,-0.594321489f,0.172160596f,0.0662852675f,0.00200063316f,-0.488704711f,0.518216193f,-0.173854038f},{-0.217394933f,0.283239871f,0.304993987f,-0.524037659f,-0.286474377f,-0.257583916f,-0.251349151f,0.430805653f,-0.396520764f,0.625854254f,-0.141423211f,0.201261088f,0.000127042978f,-0.155097604f,-0.187272221f,0.0696707219f},{-0.201948583f,-0.0893489346f,0.409126282f,0.0830287039f,-0.0911273882f,-0.397979259f,-0.639122725f,0.0919198319f,0.0893768817f,0.450609773f,-0.078373231f,-0.632291317f,6.52951276e-05f,-0.643954933f,-0.633989394f,0.544454098f},{-0.111143723f,0.33597964f,-0.159655273f,0.10873241f,0.0948703289f,0.137473017f,0.395032108f,0.0257554539f,0.13788043f,-0.18141903f,0.0414575301f,0.290307224f,-0.00309342775f,0.732113719f,0.217256889f,-0.0447250344f},{0.0111460788f,-0.670919299f,0.268736064f,0.00840315688f,-0.248389766f,-0.25056681f,-0.743429422f,-0.135137036f,0.334472477f,-0.0175607372f,-0.128635034f,-0.526257992f,-0.000346688554f,-0.422464162f,-0.329883188f,-0.311391324f},{0.155491248f,0.0404978842f,-0.163832098f,0.00235567638f,-0.256793797f,-0.303436071f,0.365359396f,0.012414162f,0.179592907f,-0.145221785f,0.266671181f,0.38721928f,2.87331363e-06f,0.49517265f,0.306317747f,-0.0108120851f},{0.148180276f,-0.119024493f,-0.0867257044f,0.0179198943f,-0.247967422f,-0.252823681f,0.358970553f,0.00644141901f,0.181819931f,-0.158808485f,0.164618343f,0.467546225f,-0.000118624295f,0.494431049f,0.134526089f,0.0839479864f}};
        static const float b2[8]={0.0183863286f,0.0187446941f,0.0333002694f,0.0079912059f,-0.0130511569f,0.0191638358f,-0.00612669159f,0.490820744f};
        float hidden[16];
        for(int j=0;j<16;++j){float z=b1[j];for(int i=0;i<32;++i)z+=w1[j][i]*x[i];hidden[j]=std::max(0.0f,z);}
        int best=0;float top=-1e30f;
        for(int j=0;j<8;++j){float z=b2[j];for(int i=0;i<16;++i)z+=w2[j][i]*hidden[i];if(z>top){top=z;best=j;}}
        return best;
    }

    int activeRule(bool build) const {
        static const int rules[8]={0,8,3,6,4,9,4,4};
        return selected_expert_==7?(build?0:rule_):((selected_expert_==6&&build)?0:rules[selected_expert_]);
    }
    int creditRule() const {int r=activeRule(false);return (r==3||r==4||r==6)?r:-1;}
    void choose(const SystemState& s,int o,int p,bool build,int64_t bytes) {
        if(forced_next_>=0){selected_expert_=forced_next_;forced_next_=-1;}
        else if(policy_mode_>=0)selected_expert_=policy_mode_;
        else if(policy_mode_==-2)selected_expert_=int((tick(s)*6364136223846793005ULL+choices_*1442695040888963407ULL)%8);
        else {auto f=features(s,o,p,build,bytes);selected_expert_=network(f);++inferences_;}
        ++choices_;
    }
    struct Victim { int o,p,id; int64_t bytes; double value,key; };
    struct Ghost { uint64_t at=0; int rule=-1; bool credited=false; int requester=-1; bool avoidable_cross=false; };
    int flags_,rule_=4,options_;
    uint64_t load_demands_=0,compensated_misses_=0;
    bool spilled_=false,first_miss_=false;
    std::array<uint64_t,512> last_{};
    std::array<float,512> heat_{};
    std::array<Ghost,512> ghost_{};
    std::array<double,8> op_heat_{},budget_{};
    std::array<uint64_t,8> op_last_{};
    std::array<double,7> loss_{};
    std::array<unsigned,7> trials_{};
    std::array<double,64> interference_{};
    std::array<uint64_t,64> interference_at_{};
    double interference(int source,int victim,uint64_t now) const {
        int i=source*8+victim;uint64_t age=now>interference_at_[i]?now-interference_at_[i]:0;
        return interference_[i]/(1.0+double(age)/256.0);
    }

    uint64_t epoch_=0,epoch_miss_=0,switched_at_=0,returns_=0,return_base_=0;
    int phase_mask_=-1;
    static uint64_t tick(const SystemState& s) {return uint64_t(s.hit_count+s.miss_count);}
    static bool probeNext(const SystemState& s) {return s.next_op.type=="PROBE";}
    static bool less(const Victim& a,const Victim& b) {
        if(a.key!=b.key)return a.key<b.key;
        if(a.bytes!=b.bytes)return a.bytes>b.bytes;
        return a.id>b.id;
    }
    static double clip(double x,double a,double b) {return std::max(a,std::min(b,x));}
    void observe(int id,int o,uint64_t now) {
        if(last_[id]==now)return;
        uint64_t age=now>last_[id]?now-last_[id]:0;
        heat_[id]=float(double(heat_[id])/(1.0+double(age)/64.0)+1.0);last_[id]=now;
        age=now>op_last_[o]?now-op_last_[o]:0;
        op_heat_[o]=op_heat_[o]/(1.0+double(age)/128.0)+1.0;op_last_[o]=now;
    }
    void observeNext(const SystemState& s) {
        if(!probeNext(s))return;
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
        if(s.operators[o].phase==Phase::PROBE){observe(o*s.num_partitions+p,o,tick(s)+1);
            double z=double(s.operators[o].partitions[p].data_size);
            gds_[o*s.num_partitions+p]=gds_clock_+(z/s.write_bandwidth+z/s.read_bandwidth+1.0)/std::max(1.0,z);}

    }
    void credit(int rule,double loss) {
        if(rule<0)return;
        loss_[rule]=trials_[rule]?0.875*loss_[rule]+0.125*loss:loss;
        ++trials_[rule];
    }
    void loaded(const SystemState& s,int o,int p) {
        int gid=o*s.num_partitions+p;double gs=double(s.operators[o].partitions[p].data_size);
        gds_[gid]=gds_clock_+(gs/s.write_bandwidth+gs/s.read_bandwidth+1.0)/std::max(1.0,gs);
        Ghost& g=ghost_[gid];
        if(!g.at)return;
        uint64_t age=tick(s)+1-g.at,width=uint64_t(std::max(64,int(s.operators.size())*s.num_partitions*2));
        if(age<=width){if(g.rule>=0 || !(flags_&64))++returns_;if(!g.credited)credit(g.rule,1.0);}
        else if(!g.credited)credit(g.rule,0.0);
        if((flags_&1024)&&age<=width&&g.avoidable_cross) {
            int edge=g.requester*8+o;
            double bytes=double(s.operators[o].partitions[p].data_size);
            interference_[edge]=interference(g.requester,o,tick(s))+bytes/s.write_bandwidth+bytes/s.read_bandwidth+1.0;
            interference_at_[edge]=tick(s);++interference_returns;
        }
        g=Ghost();
    }
    void remember(const SystemState& s,const std::vector<Action>& a,int cause) {
        for(const auto& x:a) {
            if(x.type==Action::SPILL) {
                int id=x.op_id*s.num_partitions+x.partition_id;
                if(selected_expert_==5)gds_clock_=std::max(gds_clock_,gds_[id]);
                gds_[id]=0;
                ghost_[id].at=tick(s)+1;
                // If victim and demand target cannot coexist, eviction is forced;
                // do not treat its return as evidence against a discretionary rule.
                ghost_[id].rule=((flags_&64)&&cause>=0&&s.operators[x.op_id].partitions[x.partition_id].data_size+demand_size_>s.memory_limit)?-1:cause;
                ghost_[id].credited=false;ghost_[id].requester=requester_;
                ghost_[id].avoidable_cross=requester_>=0&&requester_!=x.op_id&&s.operators[x.op_id].phase==Phase::PROBE&&
                    s.operators[x.op_id].partitions[x.partition_id].data_size+demand_size_<=s.memory_limit;
                if(x.op_id!=requester_)++cross_spills;
            } else loaded(s,x.op_id,x.partition_id);
        }
    }
    int requester_=-1;int64_t demand_size_=0;
    void allocate(const SystemState& s) {
        int k=int(s.operators.size());uint64_t now=tick(s);
        std::array<double,8> cap{},w{};std::array<bool,8> done{};
        for(const auto& op:s.operators) {
            for(const auto& x:op.partitions)cap[op.op_id]+=double(x.data_size);
            int o=op.op_id;uint64_t age=now>op_last_[o]?now-op_last_[o]:0;
            double h=op_heat_[o]/(1.0+double(age)/128.0);
            w[o]=(op.phase==Phase::PROBE?1.0:0.25)*(1.0+h);budget_[o]=0;
        }
        double remaining=double(s.memory_limit);
        for(int pass=0;pass<=k;++pass) {
            double sw=0;for(int o=0;o<k;++o)if(!done[o])sw+=w[o];
            if(sw<=0)break;
            bool capped=false;
            for(int o=0;o<k;++o)if(!done[o] && cap[o]<=remaining*w[o]/sw) {
                budget_[o]=cap[o];done[o]=true;capped=true;
            }
            if(!capped){for(int o=0;o<k;++o)if(!done[o])budget_[o]=remaining*w[o]/sw;break;}
            remaining=double(s.memory_limit);for(int o=0;o<k;++o)if(done[o])remaining-=budget_[o];
        }
        ++allocations;
    }
    void adapt(const SystemState& s,int o,int p) {
        uint64_t now=tick(s);int mask=phase_mask_;
        if(mask!=((1<<int(s.operators.size()))-1)){mask=0;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;}
        uint64_t observed_misses=(options_&8)?((options_&64)?uint64_t(s.miss_count)+compensated_misses_:load_demands_):uint64_t(s.miss_count);
        bool first=!first_miss_,urgent=returns_-return_base_>=3;
        if(!first && mask==phase_mask_ && now-epoch_<128 && observed_misses-epoch_miss_<32 && !urgent)return;
        uint64_t width=uint64_t(std::max(64,int(s.operators.size())*s.num_partitions*2));
        for(int i=0,q=int(s.operators.size())*s.num_partitions;i<q;++i){auto& g=ghost_[i];if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}}
        if(first) {
            first_miss_=true;
            if(flags_&32) {
                double a=double(s.operators[o].partitions[p].data_size)/s.memory_limit,b=-1;
                if(probeNext(s))b=double(s.operators[s.next_op.op_id].partitions[int(s.next_op.key%s.num_partitions)].data_size)/s.memory_limit;
                rule_=a<=.125?(b<=.0013453512706539845?3:4):(s.operators.size()<=1?4:3);
            }
        } else if(flags_&4) {
            double rate=std::min(1.0,double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_)));
            int desired=(flags_&256)?rule_:4;
            // Positive evidence for a repeat working set favours heat/byte;
            // sustained misses without quick returns favour observed recency.
            if(urgent && rate>.12)desired=6;
            else if(rate>.65 && !urgent && !(flags_&128))desired=3;
            if((flags_&256)&&desired==rule_&&rule_!=4&&rate>.30&&loss_[rule_]>.50)desired=4;
            double best=loss_[desired]+(trials_[desired]?0.0:.12);
            for(int r:{4,3,6})if(trials_[r]>=4 && loss_[r]+.12<best){desired=r;best=loss_[r];}
            uint64_t dwell=urgent?8:64;
            if(desired!=rule_ && now-switched_at_>=dwell) {
                // Hysteresis prevents a tiny sampled advantage triggering a switch.
                if(urgent || desired==4 || !trials_[rule_] || loss_[rule_]>best+.08 || rate>.65) {
                    rule_=desired;switched_at_=now;++switches;
                }
            }
        }
        epoch_=now;epoch_miss_=observed_misses;return_base_=returns_;phase_mask_=mask;++epochs;
        if(flags_&8)allocate(s);
    }
    std::vector<Action> plan(const SystemState& s,int64_t need,int to,int tp,bool build,int po=-1,int pp=-1) {
        int64_t deficit=need-(s.memory_limit-s.memory_used);if(deficit<=0)return {};
        int rule=activeRule(build);
        std::array<double,8> used{},factor{};factor.fill(1.0);
        bool quota=(selected_expert_==6||selected_expert_==7);
        if(build&&(options_&4)){bool has_probe=false;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)has_probe=true;if(!has_probe)quota=false;}
        if(quota) {
            if(build || !allocations)allocate(s);
            for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.in_memory)used[op.op_id]+=double(x.data_size);
            double pad=double(s.memory_limit)/(32.0*s.operators.size());
            for(unsigned o=0;o<s.operators.size();++o)factor[o]=clip((budget_[o]+pad)/(used[o]+pad),.5,2.0);
        }
        std::array<Victim,512> c;int n=0,best=-1;uint64_t now=tick(s);
        for(const auto& op:s.operators)for(const auto& x:op.partitions) {
            int o=op.op_id,p=x.partition_id,id=o*s.num_partitions+p;
            if(!x.in_memory||x.data_size<=0||(o==to&&p==tp)||(o==po&&p==pp))continue;
            double v=0,key=-double(x.data_size)/factor[o];
            if(rule==8){v=double(x.data_size)/s.write_bandwidth;key=double(x.data_size);}
            else if(rule==9){
                if(gds_[id]==0)gds_[id]=gds_clock_+(double(x.data_size)/s.write_bandwidth+double(x.data_size)/s.read_bandwidth+1.0)/double(x.data_size);
                key=gds_[id];
            }
            else if(rule==4) {
                uint64_t age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0),q=.15+.70*h/(1.0+h);
                if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)q=1.0;
                if(op.phase==Phase::BUILD)q*=.35;
                v=(double(x.data_size)/s.write_bandwidth+q*(double(x.data_size)/s.read_bandwidth+32.0))*factor[o];
                key=v/double(x.data_size);
            } else if(rule==3)key=(double(last_[id])+1.0)*factor[o];
            else if(rule==6) {
                uint64_t age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0);
                key=(1.0+h)*factor[o]/double(x.data_size);
                if(probeNext(s)&&s.next_op.op_id==o&&s.next_op.key%s.num_partitions==p)key*=16.0;
            }
            if((flags_&1024)&&requester_>=0&&requester_!=o) {
                double unit=double(s.memory_limit)*(1.0/s.write_bandwidth+1.0/s.read_bandwidth)+1.0;
                double charge=1.0+std::min(3.0,interference(requester_,o,now)/unit);
                if(rule==0)key/=charge;else {key*=charge;v*=charge;}
            }
            c[n]={o,p,id,x.data_size,v,key};if(best<0||less(c[n],c[best]))best=n;++n;
        }
        // Exact minimum immediate write bytes for <=10 eligible candidates.
        // Larger instances use size order + covering singleton, without an optimality claim.
        if(rule==8&&n<=10){
            int64_t best_bytes=INT64_MAX;unsigned best_mask=0;
            std::array<int64_t,1024> sums;sums[0]=0;unsigned count=1;
            for(int i=0;i<n;++i){
                for(unsigned j=0;j<count;++j){unsigned mask=count+j;sums[mask]=sums[j]+c[i].bytes;
                    if(sums[mask]>=deficit&&sums[mask]<best_bytes){best_bytes=sums[mask];best_mask=mask;}}
                count*=2;
            }
            std::vector<Action> a;a.reserve(n+2);
            for(int i=0;i<n;++i)if(best_mask&(1u<<i))a.emplace_back(Action::SPILL,c[i].o,c[i].p);
            return a;
        }
        // The sorted greedy prefix has length one in this case. Select the
        // same minimum-cost covering singleton in O(Q), preserving tie order.
        if((flags_&16) && best>=0 && c[best].bytes>=deficit) {
            int chosen=best;
            if(rule==4||rule==8)for(int i=0;i<n;++i)if(c[i].bytes>=deficit &&
                (c[i].value<c[chosen].value || (c[i].value==c[chosen].value&&less(c[i],c[chosen]))))chosen=i;
            ++linear_plans;std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[chosen].o,c[chosen].p);return a;
        }
        // Exact shortcut for a sorted greedy prefix of length two.
        // No heuristic truncation: all covering singletons are still compared.
        if(best>=0&&c[best].bytes<deficit) {
            int second=-1;
            for(int i=0;i<n;++i)if(i!=best&&(second<0||less(c[i],c[second])))second=i;
            if(second>=0&&c[best].bytes+c[second].bytes>=deficit) {
                int64_t freed=c[best].bytes+c[second].bytes;
                double value=c[best].value+c[second].value;int single=-1;
                if(rule==4||rule==8)for(int i=0;i<n;++i)if(c[i].bytes>=deficit) {
                    if(c[i].value<value){single=i;value=c[i].value;}
                    else if(single>=0&&c[i].value==value&&less(c[i],c[single]))single=i;
                }
                std::vector<Action> a;a.reserve(2+(build?0:2));
                if(single>=0)a.emplace_back(Action::SPILL,c[single].o,c[single].p);
                else {
                    for(int i:{best,second}) {
                        if((rule==4||rule==8)&&freed-c[i].bytes>=deficit)freed-=c[i].bytes;
                        else a.emplace_back(Action::SPILL,c[i].o,c[i].p);
                    }
                }
                ++prefix2_plans;return a;
            }
        }
        ++sorted_plans;std::sort(c.begin(),c.begin()+n,less);
        int take=0;int64_t freed=0;double value=0;
        while(take<n&&freed<deficit){freed+=c[take].bytes;value+=c[take].value;++take;}
        if(rule==4||rule==8) {
            int single=-1;for(int i=0;i<n;++i)if(c[i].bytes>=deficit&&c[i].value<value){single=i;value=c[i].value;}
            if(single>=0){std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[single].o,c[single].p);return a;}
        }
        std::vector<Action> a;a.reserve(take+(build?0:2));
        for(int i=0;i<take;++i)if((rule==4||rule==8)&&freed-c[i].bytes>=deficit)freed-=c[i].bytes;
        else a.emplace_back(Action::SPILL,c[i].o,c[i].p);
        return a;
    }
    static int64_t written(const SystemState& s,const std::vector<Action>& a) {
        int64_t n=0;for(const auto& x:a)if(x.type==Action::SPILL)n+=s.operators[x.op_id].partitions[x.partition_id].data_size;return n;
    }
    // Local certificate: any resident x with size(x)>M-size(B) MUST leave
    // before B can be loaded. Only prefetch when these forced victims suffice.
    bool forced(const SystemState& s,int o,int p,int64_t need,std::vector<Action>& a,int64_t freed) {
        if(!(flags_&2)||need<s.memory_limit/2)return false;
        int64_t deficit=need-(s.memory_limit-s.memory_used+freed);if(deficit<=0)return true;
        std::array<bool,512> removed{};
        for(const auto& x:a)if(x.type==Action::SPILL)removed[x.op_id*s.num_partitions+x.partition_id]=true;
        std::vector<Action> extra;int64_t sum=0;
        for(const auto& op:s.operators)for(const auto& x:op.partitions) {
            if(x.in_memory&&x.data_size>s.memory_limit-need&&!removed[op.op_id*s.num_partitions+x.partition_id]&&!(op.op_id==o&&x.partition_id==p)) {
                extra.emplace_back(Action::SPILL,op.op_id,x.partition_id);sum+=x.data_size;
            }
        }
        if(sum<deficit)return false;
        a.insert(a.end(),extra.begin(),extra.end());++certified_prefetches;return true;
    }
public:

    void forceNext(int x){forced_next_=x;}
    void setMode(int x){policy_mode_=x;}
    int lastExpert() const{return selected_expert_;}
    uint64_t inferenceCount() const{return inferences_;}
    std::array<float,32> features(const SystemState& s,int o,int p,bool build,int64_t bytes) const {
        std::array<float,32> f{};double m=double(s.memory_limit),sum=0,sq=0,mx=0,mn=m,bld=0,prb=0,own=0,total=0,own_total=0,heat=0;int nr=0;
        uint64_t now=tick(s);
        for(const auto& op:s.operators)for(const auto& x:op.partitions){
            total+=x.data_size;if(op.op_id==o)own_total+=x.data_size;
            if(!x.in_memory||x.data_size<=0)continue;
            double z=double(x.data_size);sum+=z;sq+=z*z;mx=std::max(mx,z);mn=std::min(mn,z);++nr;
            if(op.phase==Phase::BUILD)bld+=z;else prb+=z;if(op.op_id==o)own+=z;
            int id=op.op_id*s.num_partitions+x.partition_id;uint64_t age=now>last_[id]?now-last_[id]:0;
            heat+=double(heat_[id])/(1.0+double(age)/64.0);
        }
        double free=double(s.memory_limit-s.memory_used),size=double(bytes),q=double(s.operators.size()*s.num_partitions);
        const auto& target=s.operators[o].partitions[p];int tid=o*s.num_partitions+p;uint64_t age=now>last_[tid]?now-last_[tid]:0;
        double h=double(heat_[tid])/(1.0+double(age)/64.0),avg=heat/std::max(1,nr);
        f[0]=float(s.memory_used/m);f[1]=float(size/m);f[2]=float(std::max(0.0,size-free)/m);f[3]=float(free/m);
        f[4]=float(s.operators.size()/8.0);f[5]=float(s.num_partitions/64.0);f[6]=float(build);f[7]=float(s.operators[o].phase==Phase::PROBE);
        f[8]=float(nr/q);f[9]=float(mx/m);f[10]=nr?float(mn/m):0;f[11]=float(sum/std::max(1,nr)/m);
        f[12]=float(sq/(sum*sum+1.0));f[13]=float(bld/m);f[14]=float(prb/m);f[15]=float(own/m);f[16]=float(bounded(own_total/(8*m)));
        bool pn=s.next_op.type=="PROBE",in=s.next_op.type=="INSERT";f[17]=float(pn);f[18]=float(in);
        if(pn||in){int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& nx=s.operators[no].partitions[np];
            f[19]=float(nx.data_size/m);f[20]=float(nx.in_memory);f[21]=float(no==o);f[22]=float((build?target.data_size+size:size)+nx.data_size<=m);}
        f[23]=float(s.write_bandwidth/10000.0);f[24]=float(s.read_bandwidth/10000.0);
        f[25]=float(double(s.miss_count)/double(std::max(uint64_t(1),now)));
        f[26]=float(bounded(double(uint64_t(s.miss_count)+compensated_misses_-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_))));
        f[27]=float(h/(1+h));f[28]=float(avg/(1+avg));f[29]=float(bounded(double(returns_-return_base_)/double(std::max(uint64_t(1),now-epoch_))));
        f[30]=float(selected_expert_/7.0);f[31]=float(total/(m*q));return f;
    }
    uint64_t joint_loads=0,joint_rejections=0,prefix2_plans=0;
    uint64_t interference_returns=0;
    void externalSpill(){spilled_=true;}
    uint64_t switches=0,epochs=0,allocations=0,cross_spills=0,linear_plans=0,sorted_plans=0,advanced_builds=0,certified_prefetches=0;
    explicit MySpillScheduler(int mode=-1):policy_mode_(mode),flags_(351),options_(105){}
    int selectedMode() const {return rule_;}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t bytes) override {
        choose(s,o,p,true,bytes);requester_=o;demand_size_=s.operators[o].partitions[p].data_size+bytes;auto a=plan(s,bytes,o,p,true);spilled_=true;remember(s,a,-1);return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        choose(s,o,p,false,s.operators[o].partitions[p].data_size);requester_=o;++load_demands_;loaded(s,o,p);adapt(s,o,p);observe(o*s.num_partitions+p,o,tick(s));observeNext(s);
        int64_t size=s.operators[o].partitions[p].data_size;demand_size_=size;
        if((options_&1)&&probeNext(s)) {
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            int64_t limit=(options_&2)?s.memory_limit/2:((options_&16)?s.memory_limit*3/4:s.memory_limit);
            if(s.operators[no].phase==Phase::PROBE&&!b.in_memory&&!(no==o&&np==p)&&size+b.data_size<=limit&&
                (!(options_&64)||(activeRule(false)==6&&size+b.data_size<=s.memory_limit/2&&std::max(size,b.data_size)<=2*std::min(size,b.data_size)))) {
                auto a=plan(s,size+b.data_size,o,p,false);
                bool accept=true;
                int64_t tolerance=std::max(int64_t(16),(size+b.data_size)/256),sum=0;
                if(options_&(32|64))for(const auto& v:a){
                    int64_t bytes=s.operators[v.op_id].partitions[v.partition_id].data_size;sum+=bytes;
                    if(bytes>((options_&64)?std::max(size,b.data_size)+tolerance:size+b.data_size))accept=false;
                }
                if((options_&64)&&sum>size+b.data_size+tolerance)accept=false;
                if(accept){
                    if(options_&64){
                        int64_t prefix=0,needed=size-(s.memory_limit-s.memory_used);
                        for(const auto& v:a){if(prefix>=needed)break;prefix+=s.operators[v.op_id].partitions[v.partition_id].data_size;}
                        if(s.memory_limit-s.memory_used+prefix<size+b.data_size)++compensated_misses_;
                    }
                    if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                    a.emplace_back(Action::LOAD,no,np);a.emplace_back(Action::LOAD,o,p);
                    ++load_demands_;++joint_loads;demand_size_=size+b.data_size;remember(s,a,creditRule());return a;
                }
                ++joint_rejections;
            }
        }
        auto a=plan(s,size,o,p,false);if(a.capacity()<a.size()+2)a.reserve(a.size()+2);int64_t freed=written(s,a);
        if(probeNext(s)) {
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            if(s.operators[no].phase==Phase::PROBE&&!(no==o&&np==p)&&size+b.data_size<=s.memory_limit) {
                bool evicts=false;for(const auto& x:a)if(x.op_id==no&&x.partition_id==np)evicts=true;
                if(b.in_memory&&evicts) {
                    auto other=plan(s,size,o,p,false,no,np);int64_t f=written(s,other);
                    if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0){a.swap(other);freed=f;}
                }
                // Forced-victim prefetch is used at periodic callbacks only.
                // Here the existing no-extra-spill joint load remains cheaper.
                if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit){a.emplace_back(Action::LOAD,no,np);++load_demands_;}
            }
        }
        a.emplace_back(Action::LOAD,o,p);remember(s,a,creditRule());return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if((flags_&1)&&s.next_op.type=="INSERT") {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].partitions[p].in_memory&&s.next_op.tuple_size>s.memory_limit-s.memory_used) {
                choose(s,o,p,true,s.next_op.tuple_size);requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;auto a=plan(s,s.next_op.tuple_size,o,p,true);spilled_=true;remember(s,a,-1);++advanced_builds;return a;
            }
            return {};
        }
        if(!spilled_||!probeNext(s))return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE)return {};
        observe(o*s.num_partitions+p,o,tick(s)+1);
        if(x.in_memory)return {};
        requester_=o;demand_size_=x.data_size;std::vector<Action> a;
        if(x.data_size<=s.memory_limit-s.memory_used||forced(s,o,p,x.data_size,a,0)) {
            ++load_demands_;a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;
        }
        return {};
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
