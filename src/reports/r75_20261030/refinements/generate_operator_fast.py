from pathlib import Path
import hashlib,json
here=Path(__file__).resolve().parent;root=here.parents[1]
base=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_text(encoding='utf-8')
risk=(root/'tmp/r74_fast/risk.hpp').read_text(encoding='utf-8')
assert base.count(risk)==1
op=risk.replace('namespace r74 {','namespace r75op {').replace('/512.','/128.').replace('*512.','*128.')
code=base.replace('class MySpillScheduler : public SpillScheduler {',op+'\nclass MySpillScheduler : public SpillScheduler {',1)
code=code.replace('std::vector<r74::Risk> risk_, operator_risk_;',
    'std::vector<r74::Risk> risk_; std::vector<r75op::Risk> operator_risk_;')
needle='operator_risk_.assign(s.operators.size(),r74::Risk{});'
assert code.count(needle)==1
code=code.replace(needle,'operator_risk_.assign(s.operators.size(),r75op::Risk{});')
path=here/'R75_operator_fast.policy.cpp';path.write_text(code,encoding='utf-8')
(here/'operator_fast.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    operator_horizon=128,partition_horizon=512,priority_mapping_unchanged=True),indent=2)+'\n')
