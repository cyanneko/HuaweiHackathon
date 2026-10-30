"""Pure heuristic ablations: scale history by visible cache capacity in objects."""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parents[1];out=Path(__file__).resolve().parent
base=(BASE/'MySpillScheduler.cpp').read_text()
records={}
for factor in [.5,1.,2.]:
 s=base.replace('bool active_ = false;', 'bool active_ = false;\n    double scale_=64.;')
 s=s.replace('256.0 / (256.0 + static_cast<double>(q - h.last))','(4.*scale_) / (4.*scale_ + static_cast<double>(q - h.last))')
 s=s.replace('''        const int64_t now = s.hit_count + s.miss_count + 1;''','''        double total_size=0;int nonempty=0;
        for(const auto& o:s.operators)for(const auto& p:o.partitions)
            if(p.data_size>0){total_size+=p.data_size;++nonempty;}
        scale_=std::max(4.,std::min(512.,FACTOR*s.memory_limit*nonempty/std::max(1.,total_size)));
        const int64_t now = s.hit_count + s.miss_count + 1;'''.replace('FACTOR',str(factor)))
 s=s.replace('(age + 1.0) / 64.0','(age + 1.0) / scale_')
 name=f'pure_capacity{int(factor*100)}';p=out/(name+'.cpp');p.write_text(s)
 records[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'capacity_scale':factor,'minimum_scale':4,'maximum_scale':512,'observations':'legal partial probe history only; visible partition bytes for scale'}
(out/'CAPACITY_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
