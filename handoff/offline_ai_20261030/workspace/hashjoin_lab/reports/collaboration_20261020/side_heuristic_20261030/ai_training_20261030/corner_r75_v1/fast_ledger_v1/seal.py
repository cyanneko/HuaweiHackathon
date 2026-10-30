"""Seal measured gate separately from the immutable prepared protocol."""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    r=json.loads((HERE/'validation_report.json').read_text())
    assert r['status']=='EXACT_NATIVE_LEDGER_STAGE0_PASS' and len(r['primary_branches'])==89
    assert r['source_sha256']==sha(HERE/'adapter_ledger.cpp')
    assert r['native_binary_sha256']==sha(HERE/'adapter_ledger')
    assert json.loads((HERE/'cpu_released.json').read_text())['active_child_processes']==0
    handoff={'status':'VALIDATED_STAGE0_EXACT_LEDGER_AVAILABLE_WITH_HARD_PRECONDITIONS',
        'files':{p.name:sha(p) for p in [HERE/'protocol.json',HERE/'validate.py',HERE/'adapter_ledger.cpp',HERE/'adapter_ledger',HERE/'validation_report.json']},
        'checked_branches':89,'seconds':r['seconds'],'formal_D':None,
        'required_at_every_new_branch':['verify frozen input/source/binary/force SHA',
            'input canonical ids and legal ranges; INSERT only before unique per-operator SWITCH; PROBE only afterwards',
            'all forced action types and ids validated before native commit_actual can access them',
            'normal native exit and exactly one complete END and LEDGER line',
            'override_count exactly 1 for forced branches',
            'last callback all operators PROBE; nonnegative integral write/read/miss',
            'new anchor requires own original-R75-action forced control, not inherited stage0 control',
            'compute integer G from byte ledger, never rounded stdout IO',
            'capacity acceptance depends on successful original engine execution, not wrapper prediction'],
        'rejection':'Never produce approximate labels on any failed condition; keep failure artifact and use explicitly budgeted full replay only if scheduled.',
        'scope':'89 existing branches compared to independent full physical replay; future fast branches use native passive ledger with the stated conditions, not independent full Python replay.',
        'prepared_protocol_status_is_historical':True}
    (HERE/'validated_handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
    print(json.dumps({'status':handoff['status'],'handoff_sha256':sha(HERE/'validated_handoff.json')}))

if __name__=='__main__':main()
