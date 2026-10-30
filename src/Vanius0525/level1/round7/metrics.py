"""Physical-cost summaries with an explicit zero-baseline convention."""
import math
KEYS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')

def physical(row):
    return sum(row['audit']['costs'][key] for key in KEYS)

def ratio(value, baseline):
    assert math.isfinite(value) and math.isfinite(baseline)
    assert value >= 0 and baseline >= 0
    if baseline == 0:
        if value == 0:
            return 1.0
        raise ValueError('Positive cost against zero baseline: report separately, do not hide with epsilon')
    return value / baseline
