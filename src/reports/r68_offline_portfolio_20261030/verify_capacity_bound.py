"""Independent static input arithmetic; no scheduler, simulation or training."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / 'inputs/train_skewed_p3p0.txt'
raw = path.read_bytes()
lines = raw.decode().splitlines()
k, p, memory, w, r, penalty = map(int, lines[0].split())
n, interval = map(int, lines[1].split())
ops = [s.split() for s in lines[2+k:]]
assert len(ops) == n
sizes = [0] * (k*p)
seen_probe = False
probes = []
for op in ops:
    if op[0] == 'INSERT':
        assert not seen_probe, 'Bound requires no later growth'
        sizes[int(op[1])*p + int(op[2]) % p] += int(op[3])
    elif op[0] == 'PROBE':
        seen_probe = True
        probes.append(int(op[1])*p + int(op[2]) % p)
large = {i: b for i, b in enumerate(sizes) if 2*b > memory}
projection = [i for i in probes if i in large]
transitions = [(a,b) for a,b in zip(projection,projection[1:]) if a != b]
assert all(sizes[a] + sizes[b] > memory for a,b in transitions)
write_bytes = sum(sizes[a] for a,b in transitions)
read_bytes = sum(sizes[b] for a,b in transitions)
lower_g = write_bytes*r + read_bytes*w
best = json.loads((ROOT / 'snapshot/r68/runs/train_skewed_p3p0/A_incumbent/best.json').read_text())
upper_g = best['cost']['G']
result = dict(input_sha256=hashlib.sha256(raw).hexdigest(), large_partitions=large,
    projected_requests=len(projection), transitions=len(transitions),
    required_write_bytes=write_bytes, required_read_bytes=read_bytes,
    IO_lower_G=lower_g, IO_lower_cost=lower_g/(w*r),
    best_feasible_G=upper_g, best_feasible_cost=upper_g/(w*r),
    maximum_relative_gap_to_OPT=(upper_g-lower_g)/lower_g,
    maximum_remaining_reduction_from_current=(upper_g-lower_g)/upper_g,
    scope='physical IO plus miss objective; excludes decision time; prefetch allowed in IO lower bound')
out = Path(__file__).with_name('capacity_bound_verified.json')
out.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
