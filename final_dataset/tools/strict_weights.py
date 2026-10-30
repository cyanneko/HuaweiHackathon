"""Offline PROBE probabilities with explicit skew inside every operator.

Only the supplied, independently seeded RNG is used.  Returned flat weights are
the normalized joint probabilities for (op_id, partition_id), in op-major order.
This module neither generates operations nor reads scores or build layouts.

The 0.215 target TV gives sampling headroom over the target contract of 0.20;
finite observed histograms still need separate checks.  Unique floating-point
target probabilities do not imply unique, or positive, finite-sample counts.
"""

import math


FAMILIES = ('random_zipf', 'random_hotspot', 'random_lognormal')
UNIFORM_FLOOR = 0.01
TARGET_TV = 0.215
TARGET_RATIO = 2.10
_RELATIVE_SEPARATION = 1e-12


def _normalize(values):
    denominator = math.fsum(values)
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError('Weights need a finite positive sum')
    return [value / denominator for value in values]


def _tv(values):
    uniform = 1.0 / len(values)
    return 0.5 * math.fsum(abs(value - uniform) for value in values)


def _condition(log_weights):
    """Raise contrast only if necessary, preserving the local weight ordering."""
    p = len(log_weights)
    maximum = max(log_weights)
    centered = [value - maximum for value in log_weights]

    def at_power(power):
        values = _normalize([math.exp(value * power) for value in centered])
        return [(1.0 - UNIFORM_FLOOR) * value + UNIFORM_FLOOR / p
                for value in values]

    def meets(values):
        return _tv(values) >= TARGET_TV and max(values) / min(values) >= TARGET_RATIO

    initial = at_power(1.0)
    if meets(initial):
        return initial, 1.0, _tv(initial)
    lower, upper = 1.0, 2.0
    while not meets(at_power(upper)):
        lower, upper = upper, upper * 2.0
        if upper > 2.0**40:
            raise ValueError('Local weights cannot establish the required skew')
    for _ in range(60):
        middle = (lower + upper) * 0.5
        if meets(at_power(middle)):
            upper = middle
        else:
            lower = middle
    # A tiny deterministic margin keeps roundoff at the bisection boundary away
    # from the public >=0.20 threshold.  It does not consume any further RNG.
    power = upper * (1.0 + 1e-9)
    return at_power(power), power, _tv(initial)


def _separate_and_normalize(values):
    """Prevent exact float collisions, including ties created by a cold floor.

    A relative spacing much larger than one ULP survives subsequent per-operator
    normalization.  The perturbation is deterministic, recorded, and bounded in
    practice by the 512-entry input contract; no random draw or sample is retried.
    """
    adjusted = list(values)
    previous = 0.0
    altered = 0
    for index in sorted(range(len(values)), key=lambda i: (values[i], i)):
        value = adjusted[index]
        minimum = previous * (1.0 + _RELATIVE_SEPARATION)
        if value <= minimum:
            value = max(minimum, math.nextafter(previous, math.inf))
            adjusted[index] = value
            altered += 1
        previous = value
    adjusted = _normalize(adjusted)
    largest = max(range(len(adjusted)), key=adjusted.__getitem__)
    # Round the sum to precisely 1.0 in binary64 without changing the rank order.
    for _ in range(4):
        correction = 1.0 - math.fsum(adjusted)
        if correction == 0.0:
            break
        adjusted[largest] += correction
    if math.fsum(adjusted) != 1.0 or len(set(adjusted)) != len(adjusted):
        raise ArithmeticError('Joint probability normalization or uniqueness failed')
    if not all(math.isfinite(value) and value > 0 for value in adjusted):
        raise ArithmeticError('Joint probabilities must remain finite and positive')
    max_relative_change = max(abs(after - before) / before
                              for before, after in zip(values, adjusted))
    return adjusted, altered, max_relative_change


def make_weights(spec, rng, q):
    """Return (flat joint probabilities, auditable probability certificate).

    spec is a mapping containing k, p, family, shape_alpha and, for hotspot,
    hot_fraction/hot_probability.  q must equal k*p.  rng is caller-owned and must
    be separate from the RNG that generates build records and Probe samples.

    Hotspot's requested mass applies before contrast and the uniform floor; its
    actual final hot-set mass is reported.  Lognormal and Zipf keep their local
    order under contrast enhancement.  Neither operation guarantees empirical
    skew after a finite number of samples, which the dataset auditor must check.
    """
    k, p = spec['k'], spec['p']
    if not (isinstance(k, int) and isinstance(p, int) and
            1 <= k <= 8 and 2 <= p <= 64 and q == k * p):
        raise ValueError('Expected 1<=K<=8, 2<=P<=64 and q=K*P')
    family = spec['family']
    if family not in FAMILIES:
        raise ValueError('Strict partition heat requires a supported skew family')
    alpha = float(spec.get('shape_alpha', 1.2))
    if not math.isfinite(alpha) or alpha <= 0:
        raise ValueError('shape_alpha must be finite and positive')

    operator_random = _normalize([rng.lognormvariate(0.0, 0.6) for _ in range(k)])
    operator_targets = [0.5 / k + 0.5 * value for value in operator_random]
    conditional = []
    shapes = []
    hotsets = []
    for op in range(k):
        hot = []
        hot_mass_before_contrast = None
        if family == 'random_zipf':
            order = list(range(p))
            rng.shuffle(order)
            logs = [0.0] * p
            for rank, pid in enumerate(order):
                # Each local rank is independently assigned, rather than taking
                # a contiguous slice of one global ranking across all operators.
                logs[pid] = -alpha * math.log(rank + 1)
        elif family == 'random_hotspot':
            fraction = float(spec['hot_fraction'])
            probability = float(spec['hot_probability'])
            if not (math.isfinite(fraction) and 0 < fraction < 1 and
                    math.isfinite(probability) and 0 < probability < 1):
                raise ValueError('Hotspot fraction and probability must lie in (0,1)')
            hot_count = max(1, min(p - 1, round(p * fraction)))
            hot = sorted(rng.sample(range(p), hot_count))
            hot_lookup = set(hot)
            cold = [pid for pid in range(p) if pid not in hot_lookup]
            values = [0.0] * p
            hot_values = _normalize([rng.uniform(0.8, 1.2) for _ in hot])
            cold_values = _normalize([rng.uniform(0.8, 1.2) for _ in cold])
            # If nearly all P partitions are requested as hot, the requested
            # total hot mass could make each one colder than the small cold set.
            # Lift the group mass only as much as needed to preserve its name:
            # every hot partition must exceed every cold partition by 5% before
            # contrast/floor.  Both transformations preserve that ordering.
            required_odds = 1.05 * max(cold_values) / min(hot_values)
            minimum_hot_mass = required_odds / (1.0 + required_odds)
            hot_mass_before_contrast = max(probability, minimum_hot_mass)
            groups = ((hot, hot_values, hot_mass_before_contrast),
                      (cold, cold_values, 1.0 - hot_mass_before_contrast))
            for group, group_values, mass in groups:
                # Continuous within-group variation removes the old two-level
                # plateau, while each operator has both hot and cold partitions.
                for pid, value in zip(group, group_values):
                    values[pid] = mass * value
            logs = [math.log(value) for value in values]
        else:
            # Work in log space, so large but finite normal draws cannot overflow
            # when converted to probabilities by the stable softmax above.
            logs = [rng.normalvariate(0.0, alpha) for _ in range(p)]

        # The tiny deterministic offset also resolves accidental equal normal
        # draws, without turning an equal-probability plateau into apparent skew.
        logs = [value + 1e-10 * (op * p + pid + 1)
                for pid, value in enumerate(logs)]
        probabilities, power, base_tv = _condition(logs)
        conditional.append(probabilities)
        shape = dict(contrast_power=power, base_tv_from_uniform=base_tv)
        if hot_mass_before_contrast is not None:
            shape['hot_probability_before_contrast_and_floor'] = hot_mass_before_contrast
        shapes.append(shape)
        hotsets.append(hot)

    original_joint = [operator_targets[op] * conditional[op][pid]
                      for op in range(k) for pid in range(p)]
    weights, separated, max_change = _separate_and_normalize(original_joint)
    operator_probabilities = [math.fsum(weights[op * p:(op + 1) * p]) for op in range(k)]
    conditional_probabilities = [
        [value / operator_probabilities[op] for value in weights[op * p:(op + 1) * p]]
        for op in range(k)]
    per_operator = []
    for op, values in enumerate(conditional_probabilities):
        tv = _tv(values)
        ratio = max(values) / min(values)
        if tv < 0.20 or ratio < 2.0 or len(set(values)) != p:
            raise ArithmeticError('Every operator must independently satisfy the heat contract')
        if operator_probabilities[op] < 0.5 / k:
            raise ArithmeticError('Operator probability lost its requested lower bound')
        row = dict(op_id=op, tv_from_uniform=tv, hot_cold_ratio=ratio,
                   minimum_conditional_probability=min(values),
                   maximum_conditional_probability=max(values),
                   conditional_probabilities_pairwise_distinct=True,
                   entropy_nats=-math.fsum(value * math.log(value) for value in values),
                   hot_partition_ids=hotsets[op], **shapes[op])
        if family == 'random_hotspot':
            row['actual_hot_set_probability'] = math.fsum(values[pid] for pid in hotsets[op])
        per_operator.append(row)

    certificate = dict(
        schema_version=1, family=family, k=k, p=p,
        joint_probabilities=weights,
        operator_probabilities=operator_probabilities,
        conditional_probabilities=conditional_probabilities,
        per_operator=per_operator, operator_probability_targets=operator_targets,
        operator_probability_rule='0.5/K + 0.5*normalized_lognormal_draw',
        conditional_uniform_floor_before_float_separation=UNIFORM_FLOOR,
        contrast_tv_target=TARGET_TV, target_tv_required=0.20,
        target_hot_cold_ratio_required=2.0, shape_alpha=alpha,
        exact_joint_probability_sum=math.fsum(weights),
        joint_probabilities_pairwise_distinct=True,
        float_separation_adjusted_entries=separated,
        float_separation_relative_spacing=_RELATIVE_SEPARATION,
        maximum_relative_probability_adjustment=max_change,
        independent_probability_rng_required=True,
        rng_or_sample_retries=0, no_score_input=True,
        finite_count_uniqueness_or_coverage_claim=False)
    if family == 'random_hotspot':
        certificate['requested_hot_fraction'] = float(spec['hot_fraction'])
        certificate['requested_hot_probability_before_contrast_and_floor'] = float(spec['hot_probability'])
    return weights, certificate
