from pathlib import Path
import json,hashlib
here=Path(__file__).resolve().parent
base=(here/'R75_balanced.policy.cpp').read_text(encoding='utf-8')
needle='return .25+.75*std::min(1.,cov/.75);'
assert base.count(needle)==1
code=base.replace(needle,'return cov>=.75 ? 1. : .25;')
p=here/'R75_dense_switch.policy.cpp';p.write_text(code,encoding='utf-8')
(here/'dense_switch_source.json').write_text(json.dumps(dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    reason='Sparse periodic views retain the proven 25 percent visible blend; use full visible history only when its observed coverage is at least 75 percent.',
    caveat='Developed after inspecting fresh development validation; not a fresh holdout claim.'),indent=2)+'\n')
