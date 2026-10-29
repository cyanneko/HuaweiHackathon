"""Prepare/run new training-only counterfactual data on a frozen candidate."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent;D=ROOT.parent
def prepare(model,tag,data_root=None,expected_train=640):
    source=ROOT/(model+'.cpp');assert source.is_file()
    template=(D/'neural_selector/teacher.cpp').read_text('utf8')
    template=template.replace('#include "reference_types.hpp"','#include "../neural_selector/reference_types.hpp"').replace('#include "../MySpillScheduler_neural.cpp"',f'#include "{source.name}"')
    template=template.replace('int continuation=7;','int continuation=7;std::array<int,3> event_totals{},sample_totals{};')
    template=template.replace('for(int e=0;e<8;++e){Simulator b=*this;', 'for(int order=0;order<8;++order){int e=(order+pos)%8;Simulator b=*this;')
    before='*labels<<std::setprecision(10)<<"{\\"file\\":"<<quoted(filename)'
    after='*labels<<std::setprecision(10)<<"{\\"event_total\\":"<<event_totals[kind]<<",\\"event_sampled\\":"<<sample_totals[kind]<<",\\"file\\":"<<quoted(filename)'
    assert before in template;template=template.replace(before,after)
    before='std::vector<int> selected;for(int kind=0;kind<3;++kind)'
    after='std::array<int,3> event_totals{},sample_totals{};std::vector<int> selected;for(int kind=0;kind<3;++kind)'
    assert before in template;template=template.replace(before,after)
    before='for(int j=0;j<take;++j)selected.push_back(group[size_t(j)*group.size()/take]);'
    after='event_totals[kind]=int(group.size());sample_totals[kind]=take;'+before
    assert before in template;template=template.replace(before,after)
    before='second.continuation=continuation;second.run(int(x.rows.size()));'
    after='second.continuation=continuation;second.event_totals=event_totals;second.sample_totals=sample_totals;second.run(int(x.rows.size()));'
    assert before in template;template=template.replace(before,after)
    teacher=ROOT/(tag+'_teacher.cpp');teacher.write_text(template)
    paths=sorted((data_root or D/'dataset_integration_20261029/worktree/datasets').glob('*/train/*.txt'));assert len(paths)==expected_train
    (ROOT/(tag+'_paths.txt')).write_text(''.join(str(p)+'\n' for p in paths))
    meta=dict(model=model,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),teacher_sha256=hashlib.sha256(teacher.read_bytes()).hexdigest(),training_cases=len(paths),train_only=True,
        weight='event_total/event_sampled per callback kind; finite-window action value remains approximate')
    (ROOT/(tag+'_provenance.json')).write_text(json.dumps(meta,indent=2));return teacher
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model',required=True);ap.add_argument('--tag',required=True);ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--cap',type=int,default=24);ap.add_argument('--data-root',type=Path);ap.add_argument('--expected-train',type=int,default=640);a=ap.parse_args()
    teacher=prepare(a.model,a.tag,a.data_root,a.expected_train)
    if a.prepare_only:print('Prepared',teacher,flush=True);return
    p=subprocess.run(['g++','-std=c++14','-O2',str(teacher),'-o',str(ROOT/(a.tag+'_teacher'))],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    subprocess.run([str(ROOT/(a.tag+'_teacher')),str(ROOT/(a.tag+'_paths.txt')),str(ROOT/(a.tag+'_labels.jsonl')),str(a.cap),'-1','-1'],check=True,timeout=1800)
    print('Collected',a.tag,'training-only labels',flush=True)
if __name__=='__main__':main()
