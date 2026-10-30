from pathlib import Path
r=Path(__file__).resolve().parent
root=r.parents[1]
full=(root/'tmp/r74_fast/R74_fast_operator.cpp').read_bytes()
old=(root/'tmp/r74_fast/R74_fast_operator.policy.cpp').read_bytes()
prefix=full[:full.index(old)]
parent=(root/'tmp/r75_release/MySpillScheduler.cpp').read_bytes()
(r/'baseline.hpp').write_bytes(prefix+parent.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1))
