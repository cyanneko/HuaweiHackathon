# R74 fast lookup: unchanged policy, cached decay factors

The frozen R74 operator and coverage policies are copied into this directory. The only policy change is replacing the `Risk.advance` decay factor `exp(-double(delta)/512.)` with a cached lookup for integer Probe gaps 0 through 1024. Larger gaps evaluate the original expression directly. Coverage calculations, priors, 1us penalty proxy, action selection and all statistical equations remain unchanged. The original `tmp/r74_refault` files were not modified.

## Deliverables

- `R74_fast_operator.policy.cpp`, `R74_fast_coverage.policy.cpp`: independent submission classes with standard-library includes; append after official declarations.
- `R74_fast_operator.cpp`, `R74_fast_coverage.cpp`: corresponding complete official-compatible programs.
- `generate.py`: reproduces both variants directly from frozen R74 source files and records source/output SHA256 fingerprints in `source_hashes.json`.
- `risk.hpp`: identical estimator with the cached decay helper.
- `test_decay.cpp`, `test_risk.cpp`, `test_policy.cpp`: numerical and functional tests. The latter two are copied unchanged from the original R74 task.

## Initialization and cost accounting

The 1025 doubles occupy approximately 8 KiB. A function-local `static const std::array<double,1025>` is populated by calling the original exponential expression separately for every entry. There is no multiplication recurrence or namespace-scope table initialization. `Risk.advance` retains both original early returns. Thus initialization occurs only when a real nonempty statistic first needs advancement, inside the scheduler callback's timed execution. The first such invocation pays the table initialization cost, even if its particular gap uses the fallback.

Short cases may pay more initialization cost than they save; lookup/index branches, the local-static initialization guard and cache traffic also have costs. No speedup is claimed here. The parent task owns dataset equivalence checks and timed measurements. Existing R74 evidence limitations are unchanged; see the original R74 README.

## Verification completed

Built with `g++ -std=c++14 -O2 -Wall -Wextra` in the current WSL toolchain:

1. Both complete program variants compile successfully.
2. `test_decay` compares the double bit representation against the original expression for every integer delta 0..20000, the explicit 1023/1024/1025 boundary, and large gaps 100000, 1000000, and 1000000000000. All pass. A constant-factor stub failed this test before implementation.
3. Original R74 risk tests pass, including ongoing exposure, censoring and callback-frequency invariance.
4. Original R74 callback tests pass, including confirmed/ignored intents, miss versus prefetch, BUILD exclusion, duplicate next-op observations and periodic-only coverage.

One initial generation attempt encountered a legacy Windows-encoded test include; the final generator constructs the test include from the UTF-8 frozen program and policy instead. Final compilation/tests passed. Bitwise equality is verified for this toolchain and the tested delta set, not guaranteed across all compilers or math libraries.

No datasets, performance benchmarks, training, or timing comparisons were run by this implementation task.
