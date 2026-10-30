"""Attach the frozen mechanism test after an already-running campaign completes.

Does not terminate, restart or duplicate the existing campaign.
"""
import fcntl
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round5.campaign import measure
from round5.run_iteration import candidates
from round5.generate_mechanism_test import generate
from round5.audit_splits import audit


def main():
    state = ROOT / 'build/round5-mechanism-followup'
    state.mkdir(exist_ok=True)
    with (state/'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            progress = json.loads((ROOT/'build/round5-campaign/status.json').read_text())
            if progress['state'].startswith('failed'):
                raise RuntimeError('Prior campaign failed; preserve partial results and recover first')
            if progress['state'] == 'complete_needs_analysis':
                break
            (state/'status.json').write_text(json.dumps({'state': 'waiting_for_existing_campaign', 'prior_stage': progress})+'\n')
            time.sleep(30)
        sources = candidates()
        sources['ai_interval256'] = ROOT/'round5/ai_interval256_d3.cpp'
        data = ROOT/'build/round5-mechanism-test'
        if not data.exists():
            generate(data)
        report = audit({'train': ROOT/'build/data/train', 'val': ROOT/'build/data/val', 'mechanism_test': data})
        assert report['passed']
        path = ROOT/'round5/MECHANISM_SPLIT_AUDIT.json'
        if not path.exists():
            path.write_text(json.dumps(report, indent=2)+'\n')
        measure('mechanism-test-v1', data, sources)
        (state/'status.json').write_text(json.dumps({'state': 'complete_needs_analysis'})+'\n')


if __name__ == '__main__':
    main()
