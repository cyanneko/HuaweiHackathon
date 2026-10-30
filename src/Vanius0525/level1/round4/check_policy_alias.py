"""Verify the zero-effect callback-boundary control at source/machine-code levels."""
from pathlib import Path
import json,re,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/round4/policy_alias';OUT.mkdir(parents=True,exist_ok=True)
left='ai_context_exact_agg_d6_m005_support_fast';right='ai_context_callback_agg_summary_d6_m005_fast';files=[ROOT/'round4'/(n+'.cpp') for n in [left,right]]
def canonical(p):
 s=p.read_text().replace('feature_difference','difference');s=re.sub(r'//[^\n]*|/\*.*?\*/','',s,flags=re.S);return re.sub(r'\s+','',s)
same=canonical(files[0])==canonical(files[1]);sections={}
for name,binary in [(left,ROOT/'build/old_context_agg'),(right,ROOT/'build'/right)]:
 meta=json.loads(binary.with_suffix('.build.json').read_text());assert meta['scheduler_sha256']==hashlib.sha256((ROOT/'round4'/(name+'.cpp')).read_bytes()).hexdigest()
 rows={}
 for section in ['.text','.rodata','.data']:
  path=OUT/(name+section+'.bin');subprocess.run(['objcopy','--dump-section',section+'='+str(path),str(binary)],check=True,capture_output=True);rows[section]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
 sections[name]=rows
section_equal={section:sections[left][section]['sha256']==sections[right][section]['sha256'] for section in sections[left]}
result={'left':left,'right':right,'canonical_source_equal_after_local_variable_rename':same,'sections':sections,'section_equal':section_equal,'scope':'existing C++14 -O2 binaries from the same callback-val batch. Exact .text/.rodata/.data comparison; not an all-platform theorem. These are the unchanged-label summary-filter control, not the substantive exactactions ablation.'}
(ROOT/'round4/POLICY_ALIAS_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'source_equal':same,'section_equal':section_equal}),flush=True)
