// Bounded, deterministic censored-observation statistics. No solver/data access.
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
class BoundedHitV1 {
public:
    static constexpr int MAX_N=512,CAP=256,WORDS=8,STEPS=16,REFRESH=1024;
    using Mask=std::array<uint64_t,WORDS>;
    struct Block {Mask mask{};int64_t begin=0,end=0,hidden=0;int id[2]={-1,-1};uint8_t source[2]={0,0};int exact=0;};
    struct Delta {bool reset=false,block_added=false,fitted=false;Block block;};
    struct Counters {int64_t before_calls=0,epochs=0,intervals=0,hidden=0,known_hits=0,duplicate_next=0,evictions=0,fits=0,em_fits=0,analytic_fits=0,max_span=0,fit_span_sum=0,max_blocks=0;uint64_t member_visits=0;};
private:
    std::array<Block,CAP> blocks_{};
    std::array<double,MAX_N> exact_{},next_{},p_{},proposal_{},fit_next_{};
    std::array<int,CAP> group_block_{};
    std::array<double,CAP> group_count_{};
    std::array<int,512> table_{};
    int n_=0,head_=0,count_=0,live_id_=-1,exact_total_=0,next_total_=0;
    int64_t live_q_=-1,last_q_=0,last_h_=0,last_m_=0,fit_q_=-1;
    bool active_=false,committed_=false,dirty_=false;
    Mask after_{};
    Delta delta_{};Counters counters_{};
    static bool has(const Mask& m,int id){return (m[id/64]>>(id%64))&1ULL;}
    bool full(const Mask& m) const {
        for(int w=0;w<(n_+63)/64;++w){int bits=std::min(64,n_-64*w);uint64_t expected=bits==64?~0ULL:(1ULL<<bits)-1;if(m[w]!=expected)return false;}
        return true;
    }
    uint64_t hash(const Mask& m) const {uint64_t h=1469598103934665603ULL;for(int w=0;w<(n_+63)/64;++w){h^=m[w];h*=1099511628211ULL;}return h;}
    void clear(int n) {
        n_=n;head_=count_=0;live_id_=-1;live_q_=-1;exact_total_=next_total_=0;fit_q_=-1;
        exact_.fill(0);next_.fill(0);p_.fill(0);proposal_.fill(0);fit_next_.fill(0);
        for(int i=0;i<n_;++i)p_[i]=fit_next_[i]=1.0/n_;
        committed_=false;dirty_=false;
    }
    void add_exact(Block& b,int id,bool next_source) {
        if(id<0 || id>=n_ || b.exact>=2)throw std::runtime_error("bounded exact factor");
        b.id[b.exact]=id;b.source[b.exact]=next_source?1:0;++b.exact;
    }
    void push(const Block& b) {
        if(count_==CAP) {
            const auto& old=blocks_[head_];
            for(int j=0;j<old.exact;++j){--exact_[old.id[j]];--exact_total_;if(old.source[j]){--next_[old.id[j]];--next_total_;}}
            head_=(head_+1)%CAP;--count_;++counters_.evictions;
        }
        blocks_[(head_+count_)%CAP]=b;++count_;
        for(int j=0;j<b.exact;++j){++exact_[b.id[j]];++exact_total_;if(b.source[j]){++next_[b.id[j]];++next_total_;}}
        dirty_=true;++counters_.intervals;counters_.hidden+=b.hidden;counters_.max_blocks=std::max<int64_t>(counters_.max_blocks,count_);
        delta_.block_added=true;delta_.block=b;
    }
public:
    void before(int n,bool all_probe,int64_t q,int64_t hits,int64_t misses,const Mask& resident,char tag,int miss_id,int next_id) {
        ++counters_.before_calls;delta_=Delta{};
        if(n<1 || n>MAX_N)throw std::runtime_error("bounded object count");
        if(!all_probe){if(active_){clear(n);delta_.reset=true;}active_=false;return;}
        if(!active_ || n_!=n){clear(n);active_=true;delta_.reset=true;++counters_.epochs;}
        for(int w=0;w<WORDS;++w){int bits=std::min(64,std::max(0,n_-64*w));uint64_t allowed=bits==64?~0ULL:bits==0?0ULL:(1ULL<<bits)-1;if(resident[w]&~allowed)throw std::runtime_error("mask outside object range");}
        if(q!=hits+misses)throw std::runtime_error("bounded probe clock");
        if(committed_) {
            if(resident!=after_)throw std::runtime_error("bounded resident state changed outside callback");
            const int64_t dh=hits-last_h_,dm=misses-last_m_;
            if(dh<0 || dm!=(tag=='M'?1:0) || q<last_q_)throw std::runtime_error("bounded counter alignment");
            const bool executed=live_id_>=0 && live_q_>last_q_ && live_q_<=q;
            const bool known_hit=executed && has(after_,live_id_);
            if(executed && !known_hit && !(tag=='M' && live_q_==q))throw std::runtime_error("unreported known-next miss");
            if(dh<static_cast<int>(known_hit))throw std::runtime_error("bounded hidden negative");
            if(q>last_q_) {
                Block b;b.mask=after_;b.begin=last_q_;b.end=q;b.hidden=dh-static_cast<int>(known_hit);
                if(executed)add_exact(b,live_id_,true);
                if(tag=='M' && !(executed && live_q_==q))add_exact(b,miss_id,false);
                if(tag=='M' && executed && live_q_==q && live_id_!=miss_id)throw std::runtime_error("known next miss id");
                if(b.hidden>0){bool nonempty=false;for(auto x:b.mask)nonempty|=x!=0;if(!nonempty)throw std::runtime_error("hidden in empty set");}
                if(b.hidden+b.exact!=q-last_q_)throw std::runtime_error("bounded interval request conservation");
                push(b);counters_.known_hits+=known_hit;
            }
            if(executed){live_id_=-1;live_q_=-1;dirty_=true;}
        }else if(tag=='M') {
            Block b;b.begin=b.end=q;add_exact(b,miss_id,false);push(b);
        }
        if(next_id>=0) {
            if(next_id>=n_)throw std::runtime_error("bounded next id");
            if(live_id_>=0){if(live_q_!=q+1 || live_id_!=next_id)throw std::runtime_error("duplicate next mismatch");++counters_.duplicate_next;}
            else {live_id_=next_id;live_q_=q+1;dirty_=true;}
        }else if(live_id_>=0)throw std::runtime_error("unexecuted known next disappeared");
        if(count_)counters_.max_span=std::max(counters_.max_span,q-blocks_[head_].begin);
        if(dirty_ && (fit_q_<0 || q-fit_q_>=REFRESH))fit(q);
        // These values are committed together with the predicted post-action set.
        last_q_=q;last_h_=hits;last_m_=misses;
    }
    void after(const Mask& resident_after) {if(active_){after_=resident_after;committed_=true;}}
    void fit(int64_t q) {
        if(!active_)return;
        int groups=0;double anonymous=0;table_.fill(-1);
        for(int j=0;j<count_;++j) {
            const int bindex=(head_+j)%CAP;const auto& b=blocks_[bindex];
            if(!b.hidden || full(b.mask))continue;
            unsigned slot=hash(b.mask)&511U;
            while(table_[slot]>=0 && blocks_[group_block_[table_[slot]]].mask!=b.mask)slot=(slot+1)&511U;
            if(table_[slot]<0){table_[slot]=groups;group_block_[groups]=bindex;group_count_[groups]=0;++groups;}
            group_count_[table_[slot]]+=b.hidden;anonymous+=b.hidden;
        }
        const double live=live_id_>=0?1.0:0.0,denominator=exact_total_+live+anonymous+64.0;
        for(int i=0;i<n_;++i){fit_next_[i]=(next_[i]+(live_id_==i)+64.0/n_)/(next_total_+live+64.0);p_[i]=fit_next_[i];}
        if(!groups) {
            for(int i=0;i<n_;++i)p_[i]=(exact_[i]+(live_id_==i)+64.0/n_)/denominator;
            ++counters_.analytic_fits;
        }else {
            for(int step=0;step<STEPS;++step) {
                for(int i=0;i<n_;++i)proposal_[i]=exact_[i]+(live_id_==i)+64.0/n_;
                for(int g=0;g<groups;++g) {
                    const auto& mask=blocks_[group_block_[g]].mask;double mass=0;
                    for(int w=0;w<(n_+63)/64;++w)for(uint64_t bits=mask[w];bits;bits&=bits-1){mass+=p_[w*64+__builtin_ctzll(bits)];++counters_.member_visits;}
                    if(!(mass>0) || !std::isfinite(mass))throw std::runtime_error("bounded EM mass");
                    const double factor=group_count_[g]/mass;
                    for(int w=0;w<(n_+63)/64;++w)for(uint64_t bits=mask[w];bits;bits&=bits-1){int id=w*64+__builtin_ctzll(bits);proposal_[id]+=factor*p_[id];++counters_.member_visits;}
                }
                double sum=0;for(int i=0;i<n_;++i){p_[i]=proposal_[i]/denominator;if(!(p_[i]>0)||!std::isfinite(p_[i]))throw std::runtime_error("bounded probability");sum+=p_[i];}
                if(std::abs(sum-1.0)>1e-10)throw std::runtime_error("bounded normalization");
            }
            ++counters_.em_fits;
        }
        fit_q_=q;dirty_=false;delta_.fitted=true;++counters_.fits;counters_.fit_span_sum+=span(q);
    }
    int size()const{return n_;}bool active()const{return active_;}int blocks()const{return count_;}
    int liveId()const{return live_id_;}int64_t liveQ()const{return live_q_;}int64_t fitQ()const{return fit_q_;}
    int64_t span(int64_t q)const{return count_?q-blocks_[head_].begin:0;}
    int exactCount()const{return exact_total_+(live_id_>=0);}int nextCount()const{return next_total_+(live_id_>=0);}
    int64_t anonymousCount()const{int64_t count=0;for(int j=0;j<count_;++j)count+=block(j).hidden;return count;}
    int64_t constantCount()const{int64_t count=0;for(int j=0;j<count_;++j)if(full(block(j).mask))count+=block(j).hidden;return count;}
    double probability(int i)const{return p_[i];}double fittedNext(int i)const{return fit_next_[i];}
    double freshNext(int i)const{return (next_[i]+(live_id_==i)+64.0/n_)/(next_total_+(live_id_>=0)+64.0);}
    const Block& block(int j)const{return blocks_[(head_+j)%CAP];}
    const Delta& delta()const{return delta_;}const Counters& counters()const{return counters_;}
};
static_assert(sizeof(BoundedHitV1)<=65536,"bounded estimator exceeds 64KiB state budget");
