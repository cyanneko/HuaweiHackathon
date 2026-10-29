"""Pure source patch for a periodic-only, next-INSERT admission experiment.

No files are read or written and no compiler/evaluator is invoked here.  The
caller must explicitly opt in using the candidate's periodic_admission_shift.
The eight expert classes and the Overflow/Miss callbacks remain unchanged.
"""

_SIGNATURE = "    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {"
_MARKER = "// PERIODIC_ADMISSION_V1"
_OLD_BODY = (
    "                choose(s,o,p,true,s.next_op.tuple_size);requester_=o;"
    "demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;"
    "auto a=plan(s,s.next_op.tuple_size,o,p,true);spilled_=true;"
    "remember(s,a,-1);++advanced_builds;return a;"
)
_OLD_BRANCH = """        if((flags_&1)&&s.next_op.type=="INSERT") {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].partitions[p].in_memory&&s.next_op.tuple_size>s.memory_limit-s.memory_used) {
""" + _OLD_BODY + """
            }
            return {};
        }
"""


def patch(source, shift):
    """Return source with exactly the existing periodic INSERT branch patched.

    shift must be an integer in [0,3].  Unknown source layouts, a repeated patch,
    and changes outside onPeriodicAdjust are rejected rather than guessed at.
    LF and CRLF inputs preserve their original line endings outside the patch.
    """
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if type(shift) is not int or not 0 <= shift <= 3:
        raise ValueError("periodic admission shift must be an integer in [0,3]")
    if _MARKER in source:
        raise ValueError("periodic admission patch is already present")
    newline = "\r\n" if "\r\n" in source else "\n"
    if "\r" in source.replace("\r\n", ""):
        raise ValueError("unsupported line endings")
    signature = _SIGNATURE + newline
    if source.count(signature) != 1:
        raise ValueError("expected one exact onPeriodicAdjust signature")
    begin = source.index(signature)
    closer = newline + "    }" + newline + "};"
    close = source.find(closer, begin)
    if close < 0 or source.find(closer, close + len(closer)) >= 0:
        raise ValueError("expected periodic callback to be the final class method")
    end = close + len(newline + "    }")
    periodic = source[begin:end]
    old_branch = _OLD_BRANCH.replace("\n", newline)
    if periodic.count(old_branch) != 1 or source.count(old_branch) != 1:
        raise ValueError("expected one unchanged periodic INSERT overflow branch")

    # Consume choose/forceNext before either path, exactly as in the parent.
    # The safe multiplication guard also rejects a cutoff larger than M: every
    # eligible resident partition is <=M, so such a cutoff cannot be certified.
    new_body = """                choose(s,o,p,true,s.next_op.tuple_size);requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;
                // PERIODIC_ADMISSION_V1: fixed next INSERT, immediate writes only.
                const int64_t admission_size=s.operators[o].partitions[p].data_size;
                const int64_t admission_tuple=s.next_op.tuple_size;
                const int64_t admission_factor=int64_t(1)<<ADMISSION_SHIFT;
                if(admission_size>0&&admission_tuple>0&&admission_tuple<=s.memory_limit&&
                   admission_size<=s.memory_limit-admission_tuple) {
                    const int64_t admission_full=admission_size+admission_tuple;
                    if(admission_full<=s.memory_limit/admission_factor) {
                        const int64_t admission_cutoff=admission_full*admission_factor;
                        bool admission_has_other=false,admission_certified=true;
                        for(const auto& admission_op:s.operators) {
                            for(const auto& admission_part:admission_op.partitions) {
                                if(!admission_part.in_memory||admission_part.data_size<=0||
                                   (admission_op.op_id==o&&admission_part.partition_id==p))continue;
                                admission_has_other=true;
                                if(admission_part.data_size<admission_cutoff) {
                                    admission_certified=false;break;
                                }
                            }
                            if(!admission_certified)break;
                        }
                        if(admission_has_other&&admission_certified) {
                            std::vector<Action> admission_actions;admission_actions.reserve(1);
                            admission_actions.emplace_back(Action::SPILL,o,p);
                            spilled_=true;remember(s,admission_actions,-1);++advanced_builds;return admission_actions;
                        }
                    }
                }
                auto a=plan(s,s.next_op.tuple_size,o,p,true);spilled_=true;remember(s,a,-1);++advanced_builds;return a;"""
    new_body = new_body.replace("ADMISSION_SHIFT", str(shift)).replace("\n", newline)
    new_branch = old_branch.replace(_OLD_BODY, new_body, 1)
    if new_branch == old_branch or new_branch.count(_MARKER) != 1:
        raise AssertionError("internal admission patch construction failed")
    patched_periodic = periodic.replace(old_branch, new_branch, 1)
    result = source[:begin] + patched_periodic + source[end:]

    # Reversibility is a strict, byte-for-character check of the patch window;
    # in particular onMemoryOverflow, onPartitionMiss and route are untouched.
    if (result[:begin] != source[:begin] or
            result[begin + len(patched_periodic):] != source[end:] or
            patched_periodic.replace(new_branch, old_branch, 1) != periodic):
        raise AssertionError("admission patch escaped the periodic branch")
    return result
