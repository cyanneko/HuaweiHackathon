from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;root=r.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=root/'docs/superpowers/plans/2026-10-30-r85-prior-and-anchor-ablations.md'
assert sha(plan)=='7f7cd0823c62f05159cef756ad8681a541ec124ab900c929d2e7e1cc49b2294a'
parents={}
for name,prod,variant in [('R85_fast_prior8','r81_two_timescale','R81_op256_cond2048'),('R85_hier_anchor','r80_lazy_transfer','R80_next_hier_fast100'),('paired_reference','r80_lazy_transfer','R80_paired_hier_fast100')]:
 m=next(v for v in json.loads((root/'tmp'/prod/'producer.json').read_text())['variants'] if v['name']==variant)
 src=root/m['source_path'];full=root/m['translation_unit_path'];assert sha(src)==m['source_sha256'] and sha(full)==m['translation_unit_sha256']
 prefix,suffix=full.read_bytes().split(src.read_bytes());parents[name]=m
 d=r/name;d.mkdir(exist_ok=True)
 public=src.read_bytes().replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1)
 (d/'parent_test_include.hpp').write_bytes(prefix+public)
 if name!='paired_reference':
  (d/'test_callbacks.cpp').write_bytes((root/'tmp/r80_lazy_transfer/R80_next_hier_fast100/test_callbacks.cpp').read_bytes())
  (d/'test_legality.cpp').write_bytes((root/'tmp/r81_two_timescale/R81_op256_cond2048/test_legality.cpp').read_bytes())
text=(root/'tmp/r81_two_timescale/test_oracle.cpp').read_text()
text=text.replace('(f[o]+64./k)/(ft+64)','(f[o]+8.009479828345365/k)/(ft+8.009479828345365)')
text=text.replace('(x.fast_operator_[id/3].mass+32)/(x.fast_probability_total_+64)','(x.fast_operator_[id/3].mass+8.009479828345365/2)/(x.fast_probability_total_+8.009479828345365)')
text=text.replace('int main(){','int main(){\n assert(near(8.009479828345365,64*(-std::expm1(-std::log(2.)/2048))/(-std::expm1(-std::log(2.)/256))));',1)
(r/'test_prior.cpp').write_text(text)
(r/'test_transfer.cpp').write_bytes((root/'tmp/r80_lazy_transfer/R80_paired_hier_fast100/test_transfer.cpp').read_bytes())
freeze={'plan_path':str(plan.relative_to(root)),'plan_sha256':sha(plan),'parents':parents,'tests':{p.name:sha(p) for p in [r/'test_prior.cpp',r/'test_anchor.cpp',r/'test_transfer.cpp']},'scope':'two independent variants; no performance runs, no data generation; 90s compile/test window'}
(r/'prepared.json').write_text(json.dumps(freeze,indent=2)+'\n')
(r/'progress.md').write_text('# R85 implementation ledger\nPlan: '+str(plan.relative_to(root))+'\nPre-flight: independent parents; shared official declarations and callback tests only.\nRuling: use authorized tmp/r85_ablations isolation, no Git writes/commits or workspace deletion. Root will perform independent review.\nTests frozen before production generation. Red A uses frozen R81; red B uses frozen old paired to expose its non-hierarchy empty-evidence anchor.\n')
print(json.dumps({'status':'PREPARED','prepared_sha256':sha(r/'prepared.json')}))
