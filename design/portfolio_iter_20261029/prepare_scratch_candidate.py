"""Prepare an action-equivalent buffer-reuse experiment, without timing it."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
def main():
    source=ROOT/'tree_search_g1_1.json';obj=json.loads(source.read_text('utf8'))
    assert obj.get('forced_cover') and not obj.get('shared_scratch')
    obj['shared_scratch']=True
    obj['buffer_reuse_experiment']=dict(parent=source.name,parent_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),candidate_arrays=512,subset_sums=1024,expected_semantics='Only storage duration changes; all live candidate/sum elements are reassigned before reading. Callbacks are sequential.',
        acceptance_before_timing='All 785 input action hashes and IO/hit/miss equal parent; mean total D lower by at least 5% and D lower in every repeat; otherwise keep parent.')
    target=ROOT/'tree_scratch_search_g1_1.json';data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
    print(target.name)
if __name__=='__main__':main()
