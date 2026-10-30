// Decision-only return-risk kernel; all clocks use legal aggregate PROBE counts.
class RiskCore {
public:
    static constexpr int MAX_N=512,MAX_K=8;
    std::array<double,MAX_N> d{},z{};
private:
    std::array<bool,MAX_N> resident{};
    int n_=0,p_=0,live_id_=-1,checkpoint_=0;
    int64_t last_q_=0,live_q_=-1,stat_q_=0,next_checkpoint_=64;
    bool active_=false,committed_=false,ever_unknown_=false;
    const double loga_=std::log(0.5)/2048.0;
    void advance(int64_t q) {
        if(q==stat_q_)return;
        if(ever_unknown_) {
            const double a=std::exp(loga_*static_cast<double>(q-stat_q_));
            for(int i=0;i<n_;++i){d[i]*=a;z[i]*=a;}
        }
        stat_q_=q;
    }
public:
    bool active()const{return active_;}
    int size()const{return n_;}
    int64_t q()const{return last_q_;}
    void sync(){if(active_)advance(last_q_);}
    template<class P> void before(const SystemState& s,char tag,int miss_id,P probability) {
        bool all=true;for(const auto& op:s.operators)all=all&&op.phase==Phase::PROBE;
        if(!all){active_=committed_=false;return;}
        const int64_t qnow=s.hit_count+s.miss_count;
        if(!active_) {
            active_=true;committed_=false;ever_unknown_=false;
            p_=s.num_partitions;n_=s.operators.size()*p_;
            d.fill(0);z.fill(0);live_id_=-1;live_q_=-1;stat_q_=qnow;
            for(const auto& op:s.operators)for(const auto& pa:op.partitions)
                resident[op.op_id*p_+pa.partition_id]=pa.in_memory;
        }
        if(committed_) {
            const int64_t len=qnow-last_q_;
            const bool known=live_id_>=0 && live_q_>last_q_ && live_q_<=qnow;
            const int64_t known_q=live_q_;
            const int64_t unknown=len-static_cast<int>(known);
            const bool event=tag=='M' && !(known&&known_q==qnow);
            if(unknown>0) {
                advance(last_q_);
                const double decay=std::exp(loga_*static_cast<double>(len));
                double weight=-std::expm1(loga_*static_cast<double>(len))/(-std::expm1(loga_));
                if(known)weight-=std::exp(loga_*static_cast<double>(qnow-known_q));
                for(int i=0;i<n_;++i) {
                    d[i]*=decay;z[i]*=decay;
                    if(!resident[i]) {
                        z[i]+=probability(i)*weight;
                        if(event&&i==miss_id)d[i]+=1;
                    }
                }
                stat_q_=qnow;ever_unknown_=true;
            }
            if(known){live_id_=-1;live_q_=-1;}
        }
        int next=-1;
        if(s.next_op.type=="PROBE")next=s.next_op.op_id*p_+s.next_op.key%p_;
        if(next>=0 && live_id_<0){live_id_=next;live_q_=qnow+1;}
        last_q_=qnow;
    }
    void after(const SystemState&,const std::vector<Action>& actions) {
        if(!active_)return;
        for(const auto& a:actions)
            resident[a.op_id*p_+a.partition_id]=a.type==Action::LOAD;
        committed_=true;
        // Preserve the original legal sparse sync cadence, without diagnostics.
        if(last_q_>=next_checkpoint_) {
            sync();const int thresholds[4]={64,256,1024,4096};++checkpoint_;
            next_checkpoint_=checkpoint_<4?thresholds[checkpoint_]:((last_q_/65536)+1)*65536;
        }
    }
    template<class P> double future(const SystemState& s,const std::vector<int>& sign,
                                     double base_future,P probability,int mode) {
        if(!ever_unknown_)return base_future;
        advance(s.hit_count+s.miss_count);
        std::array<double,MAX_K> gd{},gz{};
        double all_d=0,all_z=0;
        if(mode==0)for(int i=0;i<n_;++i){gd[i/p_]+=d[i];gz[i/p_]+=z[i];}
        if(mode==2)for(int i=0;i<n_;++i){all_d+=d[i];all_z+=z[i];}
        const double global=(1.0+all_d)/(1.0+all_z);
        double value=0;
        for(int i=0;i<n_;++i)if(sign[i]) {
            const double p=probability(i);double h;
            if(mode==0) {
                const double rg=(1.0+std::max(0.0,gd[i/p_]-d[i]))/(1.0+std::max(0.0,gz[i/p_]-z[i]));
                h=std::min(1.0,p*(rg+d[i])/(1.0+z[i]));
            }else if(mode==1)h=std::min(1.0,p*(1.0+d[i])/(1.0+z[i]));
            else h=std::min(1.0,p*global);
            const double bytes=s.operators[i/p_].partitions[i%p_].data_size;
            const double coef=sign[i]*(bytes/s.read_bandwidth+bytes/s.write_bandwidth+100.0);
            value+=64.0*h*coef;
        }
        return value;
    }
};
