"""Exact same-state preference diagnostics, separated from continuation offsets."""
from fractions import Fraction


def compare(keys, fixed, portfolio, ties, write_rate, read_rate):
    size = len(keys)
    if size < 2 or len(set(keys)) != size or any(len(values) != size for values in (fixed, portfolio, ties)):
        raise ValueError('aligned unique actions and at least two completed costs are required')
    if any(type(value) is not int or value < 0 for value in fixed + portfolio):
        raise ValueError('costs must be complete nonnegative integers')
    if any(after > before for before, after in zip(fixed, portfolio)):
        raise ValueError('included fixed continuation cannot regress')
    if write_rate <= 0 or read_rate <= 0:
        raise ValueError('positive physical bandwidths required')
    factor = write_rate * read_rate
    physical = lambda value: float(Fraction(value, factor))
    fmin, pmin = min(fixed), min(portfolio)
    fscale, pscale = max(fixed) - fmin, max(portfolio) - pmin
    chosen_fixed = min(range(size), key=lambda i: (fixed[i], ties[i]))
    chosen_portfolio = min(range(size), key=lambda i: (portfolio[i], ties[i]))
    fixed_set = [keys[i] for i in range(size) if fixed[i] == fmin]
    portfolio_set = [keys[i] for i in range(size) if portfolio[i] == pmin]
    gains = [before - after for before, after in zip(fixed, portfolio)]
    fixed_targets = [Fraction(value - fmin, fscale) if fscale else Fraction() for value in fixed]
    portfolio_targets = [Fraction(value - pmin, pscale) if pscale else Fraction() for value in portfolio]
    regret = portfolio[chosen_fixed] - pmin
    continuation_gain = fmin - portfolio[chosen_fixed]
    total_gain = fmin - pmin
    assert continuation_gain + regret == total_gain
    inversions, broken_ties, new_ties, all_pairs = [], [], [], []
    for i in range(size):
        for j in range(i+1, size):
            fg = fixed[j] - fixed[i]
            pg = portfolio[j] - portfolio[i]
            detail = dict(actions=[keys[i], keys[j]], fixed_signed_gap_G=fg,
                          portfolio_signed_gap_G=pg, fixed_signed_gap_us=physical(fg),
                          portfolio_signed_gap_us=physical(pg),
                          portfolio_absolute_gap_relative_to_best_cost=float(Fraction(abs(pg), pmin)) if pmin else None)
            all_pairs.append(detail)
            if fg * pg < 0:
                inversions.append(detail)
            elif fg == 0 and pg != 0:
                broken_ties.append(detail)
            elif fg != 0 and pg == 0:
                new_ties.append(detail)
    return dict(
        fixed_selected_action=keys[chosen_fixed], portfolio_selected_action=keys[chosen_portfolio],
        selected_action_changed=chosen_fixed != chosen_portfolio,
        fixed_optimal_actions=fixed_set, portfolio_optimal_actions=portfolio_set,
        optimal_set_changed=set(fixed_set) != set(portfolio_set),
        fixed_selected_is_portfolio_suboptimal=regret > 0,
        fixed_selected_portfolio_regret_G=regret, fixed_selected_portfolio_regret_us=physical(regret),
        fixed_selected_portfolio_regret_relative_to_best_cost=float(Fraction(regret, pmin)) if pmin else None,
        fixed_selected_portfolio_regret_relative_to_fixed_cost_range=float(Fraction(regret, fscale)) if fscale else None,
        portfolio_best_cost_zero=pmin == 0,
        same_first_action_continuation_gain_G=continuation_gain,
        same_first_action_continuation_gain_us=physical(continuation_gain),
        first_action_selection_gain_G=regret, first_action_selection_gain_us=physical(regret),
        total_best_suffix_gain_G=total_gain, total_best_suffix_gain_us=physical(total_gain),
        common_offset=len(set(gains)) == 1,
        common_offset_G=gains[0] if len(set(gains)) == 1 else None,
        centered_action_improvement_G=[gain - gains[chosen_fixed] for gain in gains],
        normalized_target_changes=[keys[i] for i in range(size) if fixed_targets[i] != portfolio_targets[i]],
        fixed_targets=[float(value) for value in fixed_targets],
        portfolio_targets=[float(value) for value in portfolio_targets],
        strict_pair_reversals=inversions, fixed_tie_broken_pairs=broken_ties, newly_tied_pairs=new_ties,
        all_pair_gaps=all_pairs,
        all_unordered_pairs=size*(size-1)//2,
        fixed_strict_pairs=sum(fixed[i] != fixed[j] for i in range(size) for j in range(i+1,size)),
        cost_scope='same-state current action plus complete suffix; no D; finite H, not Q*')
