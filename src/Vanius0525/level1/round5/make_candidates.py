"""Controlled pool-recall ablation and low-frequency routing pilot.

The routing pilot reuses the frozen one-prefix teacher. Refreshing a choice is
an intentional distribution-shift diagnostic, not a newly validated teacher.
"""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'round4'))
from lazy_gate_family import source


def generate():
    parent = (ROOT / 'MySpillSchedulerBest.cpp').read_text()
    marker = '            if(best_mask) {'
    assert parent.count(marker) == 1
    # Compare every covering singleton with the existing top4 subset under
    # exactly the same loss, including the existing next protection.
    extra = '''            const Victim* singleton=nullptr;
            for(const auto& v:victims_) if(v.bytes>=need) {
                const double loss=v.priority*v.bytes+0.25*static_cast<double>(v.bytes)/s.write_bandwidth;
                if(loss<best_loss) {best_loss=loss;singleton=&v;}
            }
            if(singleton) {
                actions.emplace_back(Action::SPILL,singleton->op,singleton->pid);
                return;
            }
'''
    candidates = {'pure_cover_singletons': parent.replace(marker, extra + marker)}
    old = (ROOT / 'round4/ai_lazy_d2_b00_m02.cpp').read_text()
    begin = '    int gate(const float* f) const { '
    gate = old.split(begin, 1)[1].split(' }\n', 1)[0]
    # Same tree, experts, and legal shared history. Only refresh cadence changes.
    for interval in (256, 1024):
        s = source(gate)
        s = s.replace('int selected_mode_=-1;', 'int selected_mode_=-1; int64_t last_selection_=-1;')
        s = s.replace('selected_mode_=-1;', 'selected_mode_=-1;', 1)
        s = s.replace('uniform_cycle_=false;selected_mode_=-1;',
                      'uniform_cycle_=false;selected_mode_=-1;last_selection_=-1;')
        s = s.replace('if(selected_mode_<0 && observed_count_>=32)',
                      f'if(observed_count_>=32 && (selected_mode_<0 || observed_count_-last_selection_>={interval}))')
        s = s.replace('selected_mode_=gate(gf);', 'selected_mode_=gate(gf);last_selection_=observed_count_;')
        candidates[f'ai_refresh{interval}'] = s
    records = {}
    for name, code in candidates.items():
        path = HERE / (name + '.cpp')
        if path.exists():
            assert path.read_text() == code, 'Preserve existing candidate bytes'
        else:
            path.write_text(code)
        records[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'candidates': records,
              'pure_parent_sha256': hashlib.sha256(parent.encode()).hexdigest(),
              'tree_parent_sha256': hashlib.sha256(old.encode()).hexdigest(),
              'ai_scope': 'cadence ablation only; frozen prefix/full-suffix configuration teacher, no new fitting; repeated refresh labels are not yet aligned',
              'no_promotion': True}
    path = HERE / 'CANDIDATES.json'
    if path.exists():
        assert json.loads(path.read_text()) == record
    else:
        path.write_text(json.dumps(record, indent=2) + '\n')
    return candidates


if __name__ == '__main__':
    generate()
