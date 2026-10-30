# Fixed budget-recovery ablation analysis

PROVISIONAL: formal only when ../publication.json binds this file hash.

Original attempt remains INCOMPLETE:845 valid and one450s phase-budget timeout (not a60s per-method violation). Recovery is one fixed fresh entire lastcase, all9 methods and new Naive/D; all8 old successful lastcase measurements are excluded without best-of. Analysis846 =837 retained +9 recovery; total original+recovery attempts855.

|Method|dyna12 score|final72 score|primary50/50|merged stat10 score|
|---|---:|---:|---:|---:|
|Naive|0.000000000|0.000000000|0.000000000|0.000000000|
|Full|4.455849488|3.713166337|4.084507912|3.439812321|
|FixedShare075|4.458017537|3.639784785|4.048901161|3.408577701|
|UnifiedSlow2048|4.306732593|3.709111805|4.007922199|3.494851339|
|NoPeriodicPrefetch|4.455155689|3.710343805|4.082749747|3.445588140|
|NoNextProtection|4.434520653|3.683534013|4.059027333|3.421778951|
|UnitMissCost|4.133023835|3.207240512|3.670132173|2.602840797|
|NoStructurePolicy|4.455852364|3.713121148|4.084486756|3.439700271|
|UniformOperatorMarginal|1.725921918|3.651430345|2.688676132|3.309180302|

Native stdout Total_Score is authoritative C. Primary old dyna/final each weight0.5; stat is separate. All raw scores, losses, IO+miss/D and P50/P90/worst retained. Local observed synthetic inputs, one timing per selected method/case, conditional removals nonadditive. State/observation maintenance stays, so D is not all removable module overhead. NoPrefetch changes future miss visibility; NoStructure is a combined scan/cycle policy; unit-cost retains cold-start bandwidth eligibility. No optimization or promotion.
