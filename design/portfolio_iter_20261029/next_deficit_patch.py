"""Pure patch for additional next-PROBE write-deficit protection credit.

Only one comparison changes. Tree routes, experts, planning, state/history
updates, periodic admission and returned-action construction remain untouched.
The inherited +1us rule is a heuristic; ONLY newly accepted decisions have the
additional real-arithmetic local IO certificate described in LOCAL_PROOF.
"""
from __future__ import annotations


_MISS = '    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {'
_PERIODIC = '    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {'
_COMPARISON = 'if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0)'
_CREDIT_MARKER = 'double(std::max(int64_t(0),b.data_size-(s.memory_limit-s.memory_used+freed-size))>>'
_ALTERNATIVE = 'auto other=plan(s,size,o,p,false,no,np);int64_t f=written(s,other);'

LOCAL_PROOF = {
    'state': (
        'Current PROBE target p is being loaded. The one known next operation is '
        'PROBE q, q is initially resident, q differs from p, and size(p)+size(q)<=M. '
        'The unprotected SPILL plan a evicts q; f1=written(a). The alternative '
        'protects q and writes f2. Plans are valid and contain only SPILL actions.'
    ),
    'deficit': 'free_after_p=M-U+f1-size(p); d=max(0,size(q)-free_after_p)',
    'unprotected_lower_bound': (
        'After a and LOAD(p), q is on disk. Before q can be served it must be '
        'loaded, costing size(q)/R whether this occurs in the intervening '
        'periodic callback or on miss. With no data-changing operation between '
        'these consecutive probes, capacity forces at least d additional SPILL '
        'bytes. Additional loads can only increase the required writes.'
    ),
    'protected_cost': (
        'Protect-q plan writes f2 and retains q while LOAD(p) completes. The '
        'existing periodic PROBE path performs no IO for an already resident q. '
        'Thus, through service of q, it needs neither a q read nor another spill.'
    ),
    'common_costs': 'Initial p read and already incurred p miss penalty are common and cancel.',
    'local_dominance': '(f2-f1)/W <= size(q)/R+d/W implies no greater IO for this fixed p,q service prefix.',
    'credit': 'max(1us, floor(d/2^shift)/W), shift in {0,1,2}',
    'legacy_boundary': (
        'Keep the old size(q)/R+1us acceptance region. A decision newly accepted '
        'by the expanded comparison necessarily has credit>1us; its extra '
        'write time is then <=size(q)/R+floor(d/2^shift)/W<=size(q)/R+d/W. '
        'The inherited +1us region itself has no general IO-dominance proof.'
    ),
    'cut': 'After service of the known next q, BEFORE the periodic callback belonging to q.',
    'not_claimed': (
        'No claim that q must miss: periodic preloading may avoid its miss penalty. '
        'No bound on callback D, unknown operations after q, or full Score. '
        'Real-arithmetic certificate only; floating comparisons are not machine-certified.'
    ),
    'legal_information': 'Uses only current SystemState, one legal next_op and the two already computed plans.',
    'integer_domain': (
        'For valid plans f1,f2<=U<=M, partition sizes<=M<=4GiB. Deficit arithmetic '
        'and f2-f1 are safely int64; max(0,...) precedes the right shift.'
    ),
}


def patch(source, shift):
    """Return source with one comparison replaced; no file IO or execution."""
    if not isinstance(source, str):
        raise TypeError('source must be str')
    if type(shift) is not int or not 0 <= shift <= 2:
        raise ValueError('next_deficit_shift must be an integer in {0,1,2}')
    if _CREDIT_MARKER in source:
        raise ValueError('Next-deficit credit has already been patched')
    if source.count(_MISS) != 1 or source.count(_PERIODIC) != 1:
        raise ValueError('Expected exact miss/periodic callback boundaries')
    begin = source.index(_MISS)
    end = source.index(_PERIODIC)
    if end <= begin or source.count(_COMPARISON) != 1:
        raise ValueError('Expected one unchanged next-target protection comparison')
    miss = source[begin:end]
    if (miss.count(_COMPARISON) != 1 or miss.count(_ALTERNATIVE) != 1 or
            miss.count('if(b.in_memory&&evicts)') != 1 or
            'size+b.data_size<=s.memory_limit' not in miss or
            'if(probeNext(s))' not in miss):
        raise ValueError('Expected the protected resident next-PROBE planning context')
    comparison_at = miss.index(_COMPARISON)
    if not miss.index('if(b.in_memory&&evicts)') < miss.index(_ALTERNATIVE) < comparison_at:
        raise ValueError('Protection comparison is outside the expected branch')
    periodic = source[end:]
    if ('if(!spilled_||!probeNext(s))return {};' not in periodic or
            'if(x.in_memory)return {};' not in periodic):
        raise ValueError('Expected the resident-next-PROBE periodic path to return no actions')
    credit = _CREDIT_MARKER + str(shift) + ')/s.write_bandwidth'
    replacement = _COMPARISON.replace('+1.0)', '+std::max(1.0,' + credit + '))')
    modified_miss = miss.replace(_COMPARISON, replacement, 1)
    result = source[:begin] + modified_miss + source[end:]
    # Strict reversal proves no route, callback body, history or action-list
    # mutation escaped the single numerical comparison replacement.
    if (replacement.count(_CREDIT_MARKER) != 1 or
            result.replace(replacement, _COMPARISON, 1) != source):
        raise AssertionError('Next-deficit patch changed more than the comparison')
    return result
