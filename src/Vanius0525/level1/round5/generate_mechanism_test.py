"""Predeclared mechanism holdouts; never used for fitting or threshold choice.

These are synthetic shifts within this simulator, not the official distribution.
Once results are opened they become exposed diagnostics for subsequent rounds.
"""
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate import make_case


def generate(out):
    out = Path(out)
    out.mkdir(exist_ok=False)
    manifest = []
    for family in ('repeated_size_hot_reversal', 'coprime_dwell_reversal'):
        for i in range(8):
            seed = 510100 + i
            data, _ = make_case(seed, 'overlap', probes=16000, k=4, p=16, b=[1, 8, 64, 1000][i % 4])
            lines = data.decode().splitlines()
            sizes = [[0]*16 for _ in range(4)]
            for line in lines[6:]:
                fields = line.split()
                if fields[0] == 'INSERT':
                    sizes[int(fields[1])][int(fields[2]) % 16] += int(fields[3])
            ranked = [sorted(range(16), key=lambda p: sizes[o][p]) for o in range(4)]
            q = [0]*4
            rng = random.Random(seed+900)
            for index in range(6, len(lines)):
                fields = lines[index].split()
                if fields[0] != 'PROBE':
                    continue
                op = int(fields[1]); tick = q[op]; q[op] += 1
                if family == 'repeated_size_hot_reversal':
                    # Alternate small and large working sets multiple times.
                    active = ranked[op][:4] if (tick//509) % 2 == 0 else ranked[op][-4:]
                    pid = rng.choice(active) if rng.random() < .97 else rng.randrange(16)
                else:
                    # Non-power-of-two dwell lengths and reversed order break
                    # alignment with the original generator's chunk lengths.
                    block = tick//(37 if (tick//509) % 2 == 0 else 113)
                    pid = (op+7*block if (tick//509) % 2 == 0 else op-7*block) % 16
                fields[2] = str(pid)
                lines[index] = ' '.join(fields)
            raw = ('\n'.join(lines)+'\n').encode()
            name = f'{family}_{seed}.txt'
            (out/name).write_bytes(raw)
            manifest.append({'file': name, 'family': family, 'paired_seed_group': seed,
                             'sha256': hashlib.sha256(raw).hexdigest()})
    (out/'manifest.json').write_text(json.dumps({'cases': manifest,
        'scope': '16 cases; 8 paired generation seeds; mechanism holdout only until first inspection; no training'}, indent=2)+'\n')
    return manifest
