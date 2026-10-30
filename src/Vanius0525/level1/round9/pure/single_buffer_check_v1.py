"""Exact rational stationary bookkeeping, not a policy performance experiment."""
from fractions import Fraction as F


def verify():
    cases = [
        ('two_equal_cold_hot_core_80pct', [1, 1], [F(1, 10), F(1, 10)], 1, 1, 1),
        ('two_skew_cold', [1, 4], [F(19, 100), F(1, 100)], 1, 2, 1),
        ('three_cold', [2, 3, 7], [F(10, 100), F(7, 100), F(3, 100)], 3, 1, 4),
        ('four_cold', [1, 2, 5, 9], [F(12, 100), F(8, 100), F(3, 100), F(1, 100)], 7, 2, 5),
    ]
    out = []
    for name, sizes, p, read, write, penalty in cases:
        total = sum(p); q = [x / total for x in p]; n = len(p)
        transition = [[p[j] if i != j else 1 - total + p[i] for j in range(n)] for i in range(n)]
        assert all(sum(row) == 1 for row in transition)
        assert [sum(q[i] * transition[i][j] for i in range(n)) for j in range(n)] == q
        direct = sum(q[i] * p[j] * (F(sizes[i], write) + F(sizes[j], read) + penalty)
                     for i in range(n) for j in range(n) if i != j)
        formula = sum(p[j] * (1 - p[j] / total) * (sizes[j] * (F(1, read) + F(1, write)) + penalty) for j in range(n))
        independent_proxy = sum(p[j] * (sizes[j] * (F(1, read) + F(1, write)) + penalty) for j in range(n))
        assert direct == formula and direct <= independent_proxy
        out.append({'case': name, 'states': n, 'cold_probability': str(total),
                    'transition_stationarity_exact': True, 'enumerated_cost_exact': str(direct),
                    'formula_cost_exact': str(formula), 'independent_access_proxy_exact': str(independent_proxy)})
    return {'scope': 'Fixed core, one cold resident, all individual cold objects fit. No next, BUILD, prefetch, or core breaks. Hand-specified rational toy cases only.',
            'complete': True, 'cases': out}
