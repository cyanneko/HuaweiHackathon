# R87 primary full comparison

Frozen plan SHA: 0e3641da02e86d76ebba01f3c7a0cfaed6ff83a534d8af78f25c0d933eaf8c0d.

Fixed datasets commit c65c7b32b06a5764ce9ad4881133a3c6eb33ed17: dyna1.0 all12/tree808ce8b11f57a1a96051f22aa572eceb82b1fba0 and final2.1 eval72/tree41197783dd577dfccf5b007a6ece67cbfb241e4b. Use unchanged d70 cache; no final3 inputs, new seeds, subsampling, historical D reuse or cross-round Naive denominator.

Eight fixed methods, ordered: Naive, R75_dense_switch, R80_next_hier_fast100, R81_op256_cond2048, Van_latest, R85_fast_prior8, R85_hier_anchor, R87_fixedshare_op. First seven dictionaries exactly match frozen R85. R87's direct parent is R85_fast_prior8; existing A/B parent annotations retained. R80 paired remains in historical complete reports but is excluded from this focused round before performance.

Both complete selections must be prepared before timing. Prepare verifies full input SHA/size, sidecar SHA, header/counts and source/TU/ELF identities. Each phase starts a fresh campaign with no resume/retry. Lexicographic cases; fixed method order rotated left by case index modulo8. One repeat, serial Linux CPU, 96+576 new cells. Native core and official framework unchanged.

Execution-loop budgets: dyna1100s/final650s; each cell min(60s,remaining). Setup/copy and some teardown integrity work are outside loop accounting. Failed/timeout/missing cells stay visible; no smaller-denominator result. Complete requires exact expected valid grid, original identity, successful controller return even after last row, no controller error, terminal=valid=planned, no changed artifacts, active children0 and PASS finalization gate. Raw summary's grid complete alone is provisional.

Cost C=IO+penalty*miss+D; D is actual cumulative scheduler decision time. With same-phase same-case Naive B, score=clip(10*(1-C/B),0,10) for positive C/B denominators, otherwise0. Preserve raw 10*(1-C/B) where B>0 and all negative improvements. Dataset mean includes every case. Combined objective=(dyna mean+final mean)/2, never pooled84 mean. Report physical/D separately, per-case and family/original-split group, nearest-rank ceil(q*n) P50/P90/worst ratios, all failures, direct-parent and Van comparisons. No global50cap, D hard veto, automatic promotion, or uncertainty claim from one timing run.

Producer source/TU/ELF/parent hashes, test PASS and final active0 release are prerequisites. No immutable runner release until producer READY and explicit Root approval. Master alone writes shared Git. All old data/results remain frozen; R86 final3 is supplementary only.
