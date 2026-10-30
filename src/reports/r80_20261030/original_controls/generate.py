from pathlib import Path
import hashlib,json,difflib
r=Path(__file__).resolve().parent;root=r.parents[1];sha=lambda b:hashlib.sha256(b).hexdigest()
parent=root/'tmp/r79_adaptive_operator/R79_adaptive/MySpillScheduler.cpp';original=parent.read_bytes();assert sha(original)=='8eb171503ce6c30d8e99939dffef33b751dd96f7b276c1d4509c090d439d982d'
needle=b'1.0 / s.write_bandwidth + 1.0 / part.data_size);';assert original.count(needle)==1
penalty=original.replace(needle,b'1.0 / s.write_bandwidth + 100.0 / part.data_size);')
# Comments identify the changed surrogate; the sole behavioral change is one coefficient.
penalty=penalty.replace(b'// The true penalty is absent from SystemState. Only its documented',b'// The true penalty is absent from SystemState. A fixed 100 microsecond')
penalty=penalty.replace(b'// lower bound (1 microsecond) is used in this cost-density heuristic.',b'// surrogate is used here; it is not the hidden scoring penalty.')
extra='''
    bool probability_cache_valid_=false;
    int64_t probability_clock_=0;
    double probability_total_=0.,probability_weight2_=0.;
    std::vector<double> flat_probability_,hier_probability_;
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
        const double prior=64./n,denom=probability_total_+64.;
        for(int id=0;id<n;++id) {
            const auto& c=next_mass_[id];const auto& g=sharing_[id/p_];
            const double mass=c.mass==0. ? 0. : c.mass*probabilityDecay(std::max<int64_t>(0,probability_clock_-c.last));
            flat_probability_[id]=(mass+prior)/denom;
            hier_probability_[id]=((1.-g.share)*mass+g.share*g.mass/p_+prior)/denom;
        }
        probability_cache_valid_=true;
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
'''
shared=penalty.decode().replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {'+extra,1)
needle='    void release(const SystemState& s, int op, int pid, int64_t required,\n                 std::vector<Action>& actions) {'
if needle not in shared:needle=needle.replace('\n','\r\n')
assert shared.count(needle)==1
shared=shared.replace(needle,'    void propose(const SystemState& s, int op, int pid, int64_t required,\n                 std::vector<Action>& actions,int frequency_mode) {')
needle='            if(evidence)reuse=refaultReuse(o.op_id*p_+part.partition_id,now-1,reuse,observed_weight);';assert shared.count(needle)==1
shared=shared.replace(needle,'''            if(frequency_mode && o.phase==Phase::PROBE && !scan && !uniform_cycle_) {
                ensureProbabilities(s);const int id=o.op_id*p_+part.partition_id;
                reuse=64.*(frequency_mode==1?flat_probability_[id]:hier_probability_[id]);
            } else if(evidence)reuse=refaultReuse(o.op_id*p_+part.partition_id,now-1,reuse,observed_weight);''')
wrapper='''    void release(const SystemState& s,int op,int pid,int64_t required,std::vector<Action>& actions) {
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

'''
shared=shared.replace('    void pruneSpills(',wrapper+'    void pruneSpills(',1)
full=(root/'tmp/r74_fast/R74_fast_operator.cpp').read_bytes();old=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_bytes();assert full.count(old)==1;prefix,suffix=full.split(old)
variants=[]
for name,mode in [('R80_penalty100',0),('R80_next_flat100',1),('R80_next_hier100',2),('R80_paired_hier100',3)]:
 folder=r/name;folder.mkdir(exist_ok=True);policy=penalty if mode==0 else ('#define R80_MODE '+str(mode)+'\n'+shared).encode();(folder/'MySpillScheduler.cpp').write_bytes(policy);(folder/'main.cpp').write_bytes(prefix+policy+suffix)
 (folder/'test_include.hpp').write_bytes(prefix+policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1))
 (folder/'parent.diff').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),policy.decode().splitlines(True),fromfile='frozen_R79',tofile=name)),encoding='utf-8')
 callbacks=(root/'tmp/r74_fast/test_policy.cpp').read_text().replace('"test_policy_include.hpp"','"test_include.hpp"');(folder/'test_callbacks.cpp').write_text(callbacks,encoding='utf-8')
 variants.append(dict(name=name,source_path=(folder/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(policy),translation_unit_path=(folder/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(prefix+policy+suffix),binary='${WORKSPACE}<LOCAL_TEMP>'+name+'/scheduler',binary_sha256=None,compile_flags=['-std=c++14','-O2'],instrumented=False))
assert parent.read_bytes()==original
(r/'producer.json').write_text(json.dumps(dict(status='GENERATED_NOT_COMPILED',parent_source_sha256=sha(original),parent_unchanged=True,framework_unchanged=True,variants=variants,candidates=variants,source_manifest={'plan_sha256':sha((root/'docs/superpowers/plans/2026-10-30-r80-van-controlled-transfer.md').read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes())}),indent=2)+'\n',encoding='utf-8')
print('four isolated candidates generated')
