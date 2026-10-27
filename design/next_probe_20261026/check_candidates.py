import json
from pathlib import Path
from experiment import evaluate,dump
ROOT=Path(__file__).resolve().parent
evaluate(ROOT/'development_manifest.json',['baseline','base','guard_feedback','guard_build_feedback','guard_half_build_feedback','guard_physical'],2,'guard_development')
rows=json.loads((ROOT/'scale_manifest.json').read_text())
dump(ROOT/'scale_development_manifest.json',[r for r in rows if r['id'] in ['maxN_mixed_maxQ','maxN_growth_4GiB','resident_pressure_B1']])
evaluate(ROOT/'scale_development_manifest.json',['baseline','base','guard_feedback','guard_build_feedback','guard_physical'],1,'scale_development')
