"""Exact acceleration of the frozen generator's integer allocation loop.

Keep the same denominator/order for fsum and the same floating-point arithmetic.
Only skip entries whose original increment would be zero, and reuse a denominator
when its active set did not change. This changes execution time, not allocation.
"""
import math


def allocate(total, weights, lower, upper):
    values = list(lower)
    if not sum(lower)<=total<=sum(upper):
        raise ValueError('Requested total cannot satisfy the element bounds')
    remaining = total-sum(values)
    active = [i for i in range(len(values)) if values[i]<upper[i]]
    ranked = sorted(active,key=lambda i:weights[i],reverse=True)
    denominator = math.fsum(weights[i] for i in active)
    while remaining:
        before = remaining
        saturated = False
        for i in ranked:
            proportional = int(before*weights[i]/denominator)
            if proportional==0:
                break
            increment = min(upper[i]-values[i],proportional)
            values[i] += increment
            remaining -= increment
            saturated = saturated or values[i]==upper[i]
        if remaining==before:
            for i in active:
                if not remaining:
                    break
                values[i] += 1
                remaining -= 1
                saturated = saturated or values[i]==upper[i]
        if saturated and remaining:
            active = [i for i in active if values[i]<upper[i]]
            ranked = [i for i in ranked if values[i]<upper[i]]
            denominator = math.fsum(weights[i] for i in active)
    return values
