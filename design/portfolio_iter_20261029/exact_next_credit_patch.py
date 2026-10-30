"""Pure patch: forced-cover certificate permits an additional next-PROBE credit.

The old next-deficit-shift-0 comparison remains the first OR operand. Only if
it fails and the p-byte credit comparison can pass do we inspect the existing
protected plan's victim list. No plan signature, routing or history changes.
"""
from __future__ import annotations


_MISS = '    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {'
_PERIODIC = '    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {'
_INSERT_HELPER = '    static int64_t written(const SystemState& s,const std::vector<Action>& a) {'
_HELPER_NAME = 'exactNextVictimsForced'
_ALTERNATIVE = 'auto other=plan(s,size,o,p,false,no,np);int64_t f=written(s,other);'
_OLD_CONDITION = (
    'if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+'
    'std::max(1.0,double(std::max(int64_t(0),b.data_size-(s.memory_limit-s.memory_used+freed-size))>>0)/s.write_bandwidth))'
)

LOCAL_PROOF = {
    'preconditions': (
        'p is the current missed target; q is the one known next PROBE target. '
        'q was resident and the unprotected legal plan a spills it. p!=q and '
        'size(p)+size(q)<=M. The alternative other is a legal distinct-SPILL '
        'plan retaining q while loading p. Partition sizes do not change '
        'between these consecutive probes; data is not deleted.'
    ),
    'certificate': 'Every victim x in other has size(x)>M-size(p)-size(q).',
    'exact_cover_argument': (
        'Every returned victim is impossible beside resident p and q and '
        'therefore compulsory. Conversely a legal protected plan cannot leave '
        'any other initial resident partition with that property. Thus other '
        'contains exactly the compulsory set, and f2 is its minimum immediate '
        'write-byte total for the fixed co-residency request.'
    ),
    'case_p_resident_after_q': (
        'If unprotected execution has p and q resident at q service, it must '
        'have spilled every compulsory victim by then. Its total writes are '
        'at least f2, plus the already executed distinct q spill. It also reads '
        'q. The protected execution writes f2 and needs no q read.'
    ),
    'case_p_not_resident_after_q': (
        'p was resident at its own service and absent at q service, so at least '
        'one extra size(p)-byte SPILL occurred after the current plan a. q must '
        'also be read after a spilled it. Therefore unprotected IO, after '
        'cancelling the common initial p read, is at least f1/W+size(q)/R+size(p)/W.'
    ),
    'acceptance': (
        '(f2-f1)/W<=size(q)/R+floor(size(p)/2^shift)/W, shift in {0,1,2}, '
        'is sufficient in both cases when the certificate passes. The floor '
        'credit never exceeds the necessary size(p)/W in the second case.'
    ),
    'periodic': (
        'Periodic preloading may avoid a q miss but still pays its LOAD and any '
        'needed SPILL. In the protected branch the existing periodic PROBE '
        'path returns no IO actions when q is already resident.'
    ),
    'cut': 'After q service and BEFORE q\'s own periodic callback.',
    'not_claimed': (
        'The inherited +1us/d-credit region is unchanged and is not all covered '
        'by this certificate. No q-miss penalty is credited. Callback D, '
        'unknown future operations and complete Score have no guarantee. '
        'The proof uses real arithmetic; float comparisons are not machine-certified.'
    ),
    'work': 'Check the old guard, then p-credit, then scan only other: O(|other|), no extra partition scan or expert planning.',
    'example': {
        'cost_scope': 'IO from the current p-miss callback through q service; earlier workload IO is common and excluded.',
        'memory_bytes': 64 << 20, 'used_bytes': 55 << 20,
        'p_bytes': 16 << 20, 'q_bytes': 16 << 20, 'A_bytes': 39 << 20,
        'write_bandwidth': 1, 'read_bandwidth': 2,
        'f1_bytes': 16 << 20, 'f2_bytes': 39 << 20,
        'extra_write_us': 23 << 20, 'd_bytes': 7 << 20,
        'old_d_credit_rhs_us': 15 << 20,
        'new_shift0_rhs_us': 24 << 20,
        'protected_prefix_io_us': 47 << 20,
        'unprotected_expert1_prefix_io_us': 48 << 20,
        'only_shift0_accepts_this_example': True,
    },
}


def patch(source, shift):
    """Add one helper and one short-circuit OR to the frozen d-credit-0 source."""
    if not isinstance(source, str):
        raise TypeError('source must be str')
    if type(shift) is not int or not 0 <= shift <= 2:
        raise ValueError('exact_next_credit_shift must be an integer in {0,1,2}')
    if _HELPER_NAME in source:
        raise ValueError('Exact next-credit helper is already present')
    if (source.count(_MISS) != 1 or source.count(_PERIODIC) != 1 or
            source.count(_INSERT_HELPER) != 1 or source.count(_OLD_CONDITION) != 1):
        raise ValueError('Expected the exact next-deficit-shift-0 parent layout')
    begin, end = source.index(_MISS), source.index(_PERIODIC)
    helper_at = source.index(_INSERT_HELPER)
    if not helper_at < begin < end:
        raise ValueError('Unexpected class/callback ordering')
    miss = source[begin:end]
    if (miss.count(_OLD_CONDITION) != 1 or miss.count(_ALTERNATIVE) != 1 or
            miss.count('if(b.in_memory&&evicts)') != 1 or
            'size+b.data_size<=s.memory_limit' not in miss or
            not miss.index('if(b.in_memory&&evicts)') < miss.index(_ALTERNATIVE) < miss.index(_OLD_CONDITION)):
        raise ValueError('Expected a legal resident-q protection alternative')
    periodic = source[end:]
    if ('if(!spilled_||!probeNext(s))return {};' not in periodic or
            'if(x.in_memory)return {};' not in periodic):
        raise ValueError('Expected the resident-q periodic path to return no actions')
    newline = '\r\n' if '\r\n' in source else '\n'
    if '\r' in source.replace('\r\n', ''):
        raise ValueError('Unsupported lone-CR line endings')
    helper = '''    // Caller supplies the existing legal, distinct-SPILL protect-q plan.
    static bool exactNextVictimsForced(const SystemState& s,const std::vector<Action>& victims,int64_t current,int64_t next) {
        if(victims.empty()||current<=0||next<=0||next>s.memory_limit||current>s.memory_limit-next)return false;
        const int64_t threshold=s.memory_limit-current-next;
        for(const auto& victim:victims) {
            if(victim.type!=Action::SPILL||victim.op_id<0||unsigned(victim.op_id)>=s.operators.size())return false;
            const auto& parts=s.operators[victim.op_id].partitions;
            if(victim.partition_id<0||unsigned(victim.partition_id)>=parts.size())return false;
            const auto& part=parts[victim.partition_id];
            if(!part.in_memory||part.data_size<=threshold)return false;
        }
        return true;
    }
'''.replace('\n', newline)
    p_credit = ('double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+'
                'double(size>>' + str(shift) + ')/s.write_bandwidth')
    extension = '(' + p_credit + '&&' + _HELPER_NAME + '(s,other,size,b.data_size))'
    replacement = 'if(' + _OLD_CONDITION[3:-1] + '||' + extension + ')'
    modified = source.replace(_OLD_CONDITION, replacement, 1)
    modified = modified.replace(_INSERT_HELPER, helper + _INSERT_HELPER, 1)
    restored = modified.replace(helper + _INSERT_HELPER, _INSERT_HELPER, 1).replace(replacement, _OLD_CONDITION, 1)
    if restored != source or modified.count(_HELPER_NAME) != 2:
        raise AssertionError('Patch changed more than its helper and comparison OR')
    return modified
