"""Derive the approved single BUILD delta; no native process is started."""
import difflib
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
NAMED = ROOT / 'tmp/r81_named_20261031/MySpillScheduler.cpp'
ORIGINAL = ROOT / 'tmp/r81_two_timescale/R81_op256_cond2048'


def sha(value):
    return hashlib.sha256(value).hexdigest()


parent = NAMED.read_bytes()
assert sha(parent) == '2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617'
old_source = (ORIGINAL / 'MySpillScheduler.cpp').read_bytes()
official = (ORIGINAL / 'main.cpp').read_bytes()
assert sha(old_source) == '7f65114b43dba6d5e3b5744fbee17a0b0f5b97a0d9b1b02702e3da6c8b0fb764'
assert sha(official) == 'b410a5696230bd49af81647d31341612a021184306eb859d4955100d4fe60360'
assert official.count(old_source) == 1
prefix, suffix = official.split(old_source)
old = '''        release(s, op, pid, z, a);
        pruneSpills(s, z, a);'''
new = '''        // 冷启动全 BUILD：仅在单次即可满足需求时，选最小落盘字节数。
        const int64_t need = z - (s.memory_limit - s.memory_used);
        bool all_build = s.hit_count + s.miss_count == 0
            && s.next_op.type != "PROBE" && need > 0;
        if (all_build) {
            for (const auto& o : s.operators) {
                if (o.phase != Phase::BUILD) {
                    all_build = false;
                    break;
                }
            }
        }
        int best_op = -1, best_pid = -1;
        int64_t best_bytes = 0;
        if (all_build) {
            for (const auto& o : s.operators) {
                for (const auto& part : o.partitions) {
                    if (!part.in_memory || part.data_size <= 0
                        || (o.op_id == op && part.partition_id == pid))
                        continue;
                    if (part.data_size >= need
                        && (best_op < 0 || part.data_size < best_bytes)) {
                        best_op = o.op_id;
                        best_pid = part.partition_id;
                        best_bytes = part.data_size;
                    }
                }
            }
        }
        if (best_op >= 0) {
            probability_cache_valid_ = false;
            a.emplace_back(Action::SPILL, best_op, best_pid);
        } else {
            release(s, op, pid, z, a);
        }
        pruneSpills(s, z, a);'''
newline = '\r\n' if b'\r\n' in parent else '\n'
old = old.replace('\n', newline)
new = new.replace('\n', newline)
text = parent.decode('utf-8')
assert text.count(old) == 1
changed = text.replace(old, new).encode('utf-8')
assert changed.replace(new.encode(), old.encode()) == parent
source_path = OUT / 'MySpillScheduler.cpp'
source_path.write_bytes(changed)
tu = prefix + changed + suffix
(OUT / 'main.cpp').write_bytes(tu)
assert tu[:len(prefix)] == prefix and tu[-len(suffix):] == suffix
(OUT / 'candidate.diff').write_text(''.join(difflib.unified_diff(
    text.replace('\r\n', '\n').splitlines(True),
    changed.decode().replace('\r\n', '\n').splitlines(True),
    fromfile='R81_named/MySpillScheduler.cpp', tofile='BuildBestFit/MySpillScheduler.cpp')),
    encoding='utf-8')
# Include the unmodified official engine class (but not its main) for tiny
# semantics checks; namespaced schedulers avoid duplicate private helper names.
engine = suffix[:suffix.index(b'int main(')]
tiny_header = (prefix + b'\n#include <cmath>\n#include <array>\n#include <cstdlib>\n'
               + b'namespace baseline {\n' + parent + b'\n}\n'
               + b'namespace candidate {\n' + changed + b'\n}\n' + engine)
(OUT / 'tiny.generated.hpp').write_bytes(tiny_header)
relative = lambda p: p.relative_to(ROOT).as_posix()
files = ['MySpillScheduler.cpp', 'main.cpp', 'candidate.diff', 'tiny.cpp',
         'tiny.generated.hpp', 'DESIGN_PLAN.md', 'prepare.py']
producer = dict(
    status='PREPARED_AWAITING_ROOT_NATIVE_GO', method='BuildBestFit',
    parent_name='Full', parent_source_path=relative(NAMED), parent_source_sha256=sha(parent),
    source_path=relative(source_path), source_sha256=sha(changed),
    translation_unit_path=relative(OUT / 'main.cpp'), translation_unit_sha256=sha(tu),
    official_original_TU_sha256=sha(official), framework_prefix_sha256=sha(prefix),
    framework_suffix_sha256=sha(suffix), framework_exact_after_class_substitution=True,
    exact_delta='Only cold all-BUILD onMemoryOverflow, no observed/pending PROBE, minimum single resident victim bytes>=need excluding current target; ties traversal; no fit original fallback. update/prune/record preserved; successful shortcut invalidates probability cache.',
    compile_flags=['-std=c++14', '-O2'], new_parameters=0, native_runs=0, compile_runs=0,
    input_body_scans=0, no_automatic_promotion=True,
    tiny=dict(source=relative(OUT / 'tiny.cpp'), include=relative(OUT / 'tiny.generated.hpp'),
              red_flags=['-DEXPECT_PARENT_RED'], red_expected_exit=3,
              red_expected_stderr='TINY_FAIL: minimum_single_victim_beyond_parent_top4\n',
              green_expected_exit=0, green_expected_stdout='TINY_BUILD_PASS cases=10\n',
              native_status='NOT_RUN_ROOT_HOLD'),
    artifacts={relative(OUT / f): sha((OUT / f).read_bytes()) for f in files})
(OUT / 'producer.json').write_text(json.dumps(producer, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: producer[k] for k in ['status', 'source_path', 'source_sha256',
    'translation_unit_sha256', 'framework_exact_after_class_substitution']}, indent=2))
