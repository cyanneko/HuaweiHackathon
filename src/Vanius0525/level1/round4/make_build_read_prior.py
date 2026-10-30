"""Soft BUILD reload prior, after a Probe has been observed.
An explicit prior, never a guaranteed future read or an inferred hidden miss cost.
"""
from pathlib import Path
import hashlib,json
OUT=Path(__file__).resolve().parent;records={}
for kind,parent in [('pure','pure_set025_io_asymmetry_routecount'),('ai','ai_set025_routecount')]:
 raw=(OUT/(parent+'.cpp')).read_text();key='v.priority*v.bytes+0.25*static_cast<double>(v.bytes)/s.write_bandwidth';assert raw.count(key)==1
 for beta in [.25,1.]:
  extra='+(evidence && s.operators[v.op].phase==Phase::BUILD ? '+str(beta)+'*static_cast<double>(v.bytes)/s.read_bandwidth : 0.)'
  data=raw.replace(key,key+extra);name=f'{kind}_buildread{int(beta*100):03}';target=OUT/(name+'.cpp')
  if target.exists():assert target.read_text()==data
  else:target.write_text(data)
  records[name]={'parent':parent,'parent_sha256':hashlib.sha256(raw.encode()).hexdigest(),'sha256':hashlib.sha256(data.encode()).hexdigest(),'beta':beta,'prior':'additional beta*current_bytes/read_bandwidth for spilled BUILD objects when any Probe observed','unchanged_domain':'q=0 or all operators PROBE => prior zero, original parent expression unchanged','risk':'BUILD objects need not be probed later; penalizing them may evict a genuinely hot PROBE object. No guaranteed regret or hidden-penalty inference.','hypothesis':'mixed-phase active builders differ from completed/inactive PROBE objects; charge an explicit future-reload prior rather than disabling the whole subset rule'}
(OUT/'BUILD_READ_PRIOR_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
