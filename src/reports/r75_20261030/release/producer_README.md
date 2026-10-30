# R75 development candidate

`MySpillScheduler.cpp` is a byte-identical copy of the frozen R75 dense-switch policy. Submit only this scheduler/helper definition after the official type declarations. It has no main or engine and cannot be compiled into a standalone executable by itself.

CPU and standard library only; C++14, `g++ -std=c++14 -O2`. No hidden penalty, N, B, complete input, filesystem or external model access. The miss-cost proxy remains the inherited 1 us lower-bound heuristic, not a known real penalty.

Changes from R74: explicit operator blend 75% inside the refault branch; operator forgetting horizon128/partition512; full visible-demand scoring when deduplicated periodic peek coverage reaches75%; otherwise retain25% visible/75% refault; lazy per-release cache for operator priors.

Status: development candidate with eight self-generated 5M cases and a separately reported targeted regression, not an automatic team default or official-test guarantee. Main score versus current R74: 3.475946 to3.529315/10, total-cost ratios mean.986125 and worst1.000878, cumulative D about1.98s/case. Targeted dense case cost ratio.817941 toR74. New candidate variants have identical printed physical metrics on the main eight; their tiny score difference comes from measured D, and a single run does not establish a stable timing advantage or identical action traces.

Full Chinese evidence report: `docs/20261030_R75算子热度增强与密集观察保护.md` in the workspace. Source identity and evidence pointers are frozen in `candidate.json`. Known negative diagnostics and the slightly regressed main case remain in the report.
