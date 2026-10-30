from pathlib import Path
import hashlib,json,difflib
r=Path(__file__).resolve().parent;root=r.parents[1];sha=lambda b:hashlib.sha256(b).hexdigest()
parent=root/'tmp/r75_release/MySpillScheduler.cpp';original=parent.read_bytes();assert sha(original)=='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
code=original.decode()
extra='''
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
'''
code=code.replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {'+extra,1)
a=code.index('    double refaultReuse(');b=code.index('\n    struct History',a)
code=code[:a]+'''    double refaultReuse(int id,int64_t q,double visible,double observed_weight) {
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
''' +code[b:]
needle='            risk_.assign(n,r74::Risk{}); operator_risk_.assign(s.operators.size(),r75op::Risk{});'
assert code.count(needle)==1;code=code.replace(needle,needle+'\n            sharing_.assign(s.operators.size(),ShareGroup{});next_mass_.assign(n,NextMass{});next_sample_q_=-1;')
needle='        if (op >= 0) observe(op, pid, q);';assert code.count(needle)==1
code=code.replace(needle,'        if (op >= 0) {refreshSharing(op,q);observe(op,pid,q);}')
needle='            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);';assert code.count(needle)==1
code=code.replace(needle,'            sampleNext(s.next_op.op_id,static_cast<int>(s.next_op.key % p_),q+1);\n'+needle)
full=(root/'tmp/r74_fast/R74_fast_operator.cpp').read_bytes();old=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_bytes();assert full.count(old)==1;prefix,suffix=full.split(old)
variants=[]
for name,mode in [('R79_independent_fixed75',0),('R79_adaptive',1)]:
 folder=r/name;folder.mkdir(exist_ok=True);policy=('#define R79_ADAPTIVE '+str(mode)+'\n'+code).encode();(folder/'MySpillScheduler.cpp').write_bytes(policy);(folder/'main.cpp').write_bytes(prefix+policy+suffix)
 (folder/'test_include.hpp').write_bytes(prefix+policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1))
 (folder/'parent.diff').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),policy.decode().splitlines(True),fromfile='frozen_R75',tofile=name)),encoding='utf-8')
 callback=(root/'tmp/r74_fast/test_policy.cpp').read_text().replace('"test_policy_include.hpp"','"test_include.hpp"');(folder/'test_callbacks.cpp').write_text(callback,encoding='utf-8')
 variants.append(dict(name=name,source_path=(folder/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(policy),translation_unit_path=(folder/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(prefix+policy+suffix),binary='${WORKSPACE}<LOCAL_TEMP>'+name+'/scheduler',binary_sha256=None,compile_flags=['-std=c++14','-O2'],instrumented=False))
van=root/'tmp/r79_reference/round9/candidates/paired_penalty100.cpp';vb=van.read_bytes();folder=r/'Van_paired_penalty100';folder.mkdir(exist_ok=True);(folder/'MySpillScheduler.cpp').write_bytes(vb);(folder/'main.cpp').write_bytes(prefix+vb+suffix)
variants.append(dict(name='Van_paired_penalty100',source_path=(folder/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(vb),translation_unit_path=(folder/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(prefix+vb+suffix),binary='${WORKSPACE}<LOCAL_TEMP>',binary_sha256=None,compile_flags=['-std=c++14','-O2'],instrumented=False))
assert parent.read_bytes()==original
assert (r/'R79_independent_fixed75/MySpillScheduler.cpp').read_bytes().replace(b'#define R79_ADAPTIVE 0',b'#define R79_ADAPTIVE 1',1)==(r/'R79_adaptive/MySpillScheduler.cpp').read_bytes()
manifest=dict(status='GENERATED_NOT_COMPILED',parent_sha256=sha(original),parent_unchanged=True,framework_unchanged=True,variants=variants,candidates=variants,source_manifest={'plan_sha256':sha((root/'docs/superpowers/plans/2026-10-30-r79-adaptive-operator-sharing.md').read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes()),'van_manifest_sha256':sha((root/'tmp/r79_reference/manifest.json').read_bytes())},scope='two experimental modes only; no promotion; no benchmarks')
(r/'producer.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print('two candidates and Van TU generated')
