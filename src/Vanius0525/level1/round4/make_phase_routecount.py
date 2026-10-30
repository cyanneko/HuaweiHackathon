"""Skip impossible full-cycle analysis with a maintained necessary condition.
Every node in a confirmed n-node cycle must have its edge confidence >=3.
"""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
parents={'pure_set025_all_probe_routecount':'round4/pure_set025_all_probe.cpp','pure_set025_io_asymmetry_routecount':'round4/pure_set025_io_asymmetry.cpp'}
records={}
for name,parent in parents.items():
    original=(BASE/parent).read_text();s=original.replace('bool uniform_cycle_=false;','bool uniform_cycle_=false;\n    int confirmed_edges_=0;',1)
    key='if (confidence_[previous_id]==3) ++graph_version_;';assert key in s
    s=s.replace(key,'if (confidence_[previous_id]==3) {++graph_version_;++confirmed_edges_;}')
    key='''} else {successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}''';assert key in s
    s=s.replace(key,''' } else {
                if(confidence_[previous_id]>=3)--confirmed_edges_;
                successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;
            }''')
    key='''recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;''';assert key in s
    s=s.replace(key,key+'confirmed_edges_=0;')
    key='''        if (last_op_<0) return;''';assert s.count(key)==1
    s=s.replace(key,'''        if(confirmed_edges_!=static_cast<int>(history_.size()))return;
'''+key)
    p=OUT/(name+'.cpp');p.write_text(s)
    records[name]={'parent':parent,'parent_sha256':hashlib.sha256(original.encode()).hexdigest(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'necessary_condition':'all n successor edges have confidence>=3; a verified n-node cycle necessarily satisfies it','claim':'analysis shortcut only; no priority/observation/action change intended; test equivalence before timing'}
(OUT/'PHASE_ROUTECOUNT_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
