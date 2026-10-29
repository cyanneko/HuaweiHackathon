"""Training-only combinations of previously train-positive tree changes."""
from pathlib import Path
import copy,hashlib,json
ROOT=Path(__file__).resolve().parent
def main():
    base_path=ROOT/'tree_search_g1_1.json';base=json.loads(base_path.read_text('utf8'))
    for i,changes in enumerate([[(28,0)],[(11,2)],[(11,3),(28,4)]]):
        out=ROOT/f'tree_combine_g2_{i}.json';obj=copy.deepcopy(base);log=[]
        for node,expert in changes:
            before=obj['tree'][node]['expert'];obj['tree'][node]['expert']=expert
            log.append(dict(kind='leaf_expert',node=node,before=before,after=expert))
        obj['mutation']=dict(generation='train_positive_combinations',base=base_path.name,base_sha256=hashlib.sha256(base_path.read_bytes()).hexdigest(),changes=log,unchanged_topology=True,eval_used=False)
        obj['candidate_has_measured_fitness']=False
        raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        if out.exists():assert out.read_bytes()==raw
        else:out.write_bytes(raw)
        print(out.name)
if __name__=='__main__':main()
