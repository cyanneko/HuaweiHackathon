import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
freeze=json.loads((ROOT/'refined_freeze.json').read_text())['sources']
assert hashlib.sha256((ROOT/'MySpillScheduler_gated.cpp').read_bytes()).hexdigest()==freeze['MySpillScheduler_gated.cpp']
(ROOT.parent/'MySpillScheduler_envelope.cpp').write_bytes((ROOT/'FinalScheduler.cpp').read_bytes())
(ROOT.parent/'MySpillScheduler_final.cpp').write_bytes((ROOT/'MySpillScheduler_gated.cpp').read_bytes())
(ROOT.parent/'MySpillScheduler_prefix2.cpp').write_bytes((ROOT/'SafeBase.cpp').read_bytes())
out=dict(primary='MySpillScheduler_final.cpp',source_sha256=freeze['MySpillScheduler_gated.cpp'],options=105,
 alternate='MySpillScheduler_prefix2.cpp',alternate_sha256=freeze['SafeBase.cpp'],
 rejected_equivalent_envelope='MySpillScheduler_envelope.cpp',reason='Envelope did not improve CPU consistently; publish the already-frozen direct core.')
(ROOT/'published_sources.json').write_text(json.dumps(out,indent=2));print(out)
