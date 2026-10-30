from pathlib import Path
import hashlib,json,difflib
r=Path(__file__).resolve().parent;root=r.parents[1]
sha=lambda x:hashlib.sha256(x).hexdigest()
parent=root/'tmp/r75_release/MySpillScheduler.cpp';original=parent.read_bytes()
assert sha(original)=='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
old=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_bytes();full=(root/'tmp/r74_fast/R74_fast_operator.cpp').read_bytes();assert full.count(old)==1
prefix,suffix=full.split(old)
needle=b'active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a); pruneSpills(s,z,a); record(s,a); return a;'
assert original.count(needle)==1
body='''active_ = true; update(s); std::vector<Action> a;
        const int64_t need=z-(s.memory_limit-s.memory_used);
        int best_op=-1,best_pid=-1; int64_t best_size=0;
        if (CONDITION && need>0) {
            int next_op=-1,next_pid=-1;
            if (s.next_op.type=="PROBE" && p_>0 && s.next_op.op_id>=0 &&
                s.next_op.op_id<static_cast<int>(s.operators.size()) &&
                s.operators[s.next_op.op_id].phase==Phase::PROBE) {
                next_op=s.next_op.op_id; next_pid=static_cast<int>(s.next_op.key%p_);
            }
            for (const auto& o:s.operators) for (const auto& part:o.partitions) {
                if (!part.in_memory || part.data_size<=0 || part.data_size<need ||
                    (o.op_id==op && part.partition_id==pid) ||
                    (o.op_id==next_op && part.partition_id==next_pid)) continue;
                if (best_op<0 || part.data_size<best_size ||
                    (part.data_size==best_size && (o.op_id<best_op ||
                     (o.op_id==best_op && part.partition_id<best_pid)))) {
                    best_op=o.op_id; best_pid=part.partition_id; best_size=part.data_size;
                }
            }
        }
        if (best_op>=0) a.emplace_back(Action::SPILL,best_op,best_pid);
        else release(s,op,pid,z,a);
        pruneSpills(s,z,a); record(s,a); return a;'''
variants=[]
for name,condition in [('R78_build0_singlefit','s.hit_count+s.miss_count==0'),('R78_overflow_singlefit','true')]:
 code=original.replace(needle,body.replace('CONDITION',condition).encode())
 policy=r/(name+'.policy.cpp');tu=r/(name+'.cpp');policy.write_bytes(code);tu.write_bytes(prefix+code+suffix)
 (r/(name+'.hpp')).write_bytes(prefix+code.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1))
 (r/(name+'.diff')).write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),code.decode().splitlines(True),fromfile='frozen_R75',tofile=name)),encoding='utf-8')
 variants.append(dict(name=name,source_path=policy.relative_to(root).as_posix(),source_sha256=sha(code),translation_unit_path=tu.relative_to(root).as_posix(),translation_unit_sha256=sha(tu.read_bytes()),binary='${WORKSPACE}<LOCAL_TEMP>'+name,binary_sha256=None,compile_flags=['-std=c++14','-O2'],instrumented=False))
assert parent.read_bytes()==original
manifest=dict(status='generated_awaiting_compile',temporary=True,promoted=False,parent_sha256=sha(original),parent_bytes_unchanged=True,official_framework_unchanged=True,variants=variants,candidates=variants)
(r/'producer.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
