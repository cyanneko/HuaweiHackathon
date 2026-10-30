from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
source=root.parent/'r74_refault'
old=(source/'risk.hpp').read_text(encoding='utf-8')
helper='''inline double decay(int64_t delta) {
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
'''
new=old.replace('#include <cmath>','#include <cmath>\n#include <array>',1)
new=new.replace('namespace r74 {','namespace r74 {\n'+helper,1)
assert new.count('std::exp(-static_cast<double>(q-last)/512.)')==1
new=new.replace('std::exp(-static_cast<double>(q-last)/512.)','decay(q-last)',1)
(root/'risk.hpp').write_text(new,encoding='utf-8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'sources':{'risk.hpp':sha(source/'risk.hpp')},'outputs':{}}
for kind in ['operator','coverage']:
 for suffix in ['.policy.cpp','.cpp']:
  src=source/('R74_'+kind+suffix);dst=root/('R74_fast_'+kind+suffix)
  text=src.read_text(encoding='utf-8');assert text.count(old)==1
  dst.write_text(text.replace(old,new,1),encoding='utf-8')
  manifest['sources'][src.name]=sha(src);manifest['outputs'][dst.name]=sha(dst)
for name in ['test_risk.cpp','test_policy.cpp']:
 (root/name).write_bytes((source/name).read_bytes())
full=(root/'R74_fast_coverage.cpp').read_text(encoding='utf-8')
policy=(root/'R74_fast_coverage.policy.cpp').read_text(encoding='utf-8')
assert full.count(policy)==1
inc=full[:full.index(policy)]+policy.replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {\npublic:',1)
(root/'test_policy_include.hpp').write_text(inc,encoding='utf-8')
for name in ['risk.hpp','generate.py','test_decay.cpp','test_risk.cpp','test_policy.cpp']:
 manifest['outputs'][name]=sha(root/name)
(root/'source_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Generated frozen-source operator/coverage LUT variants')
