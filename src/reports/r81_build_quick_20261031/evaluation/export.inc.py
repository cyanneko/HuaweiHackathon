def export():
    summaries={mode:read(HERE/mode/'finalized_summary.json') for mode in COUNTS}
    assert all(s['complete'] for s in summaries.values())
    dest=HERE/'provisional';dest.mkdir(exist_ok=False)
    combined=dict(complete=True,publication_status='PROVISIONAL_REQUIRE_PUBLICATION_JSON',source_commit=SOURCE_COMMIT,methods=NAMES,dataset_case_counts=COUNTS,pooled22_mean_used=False,suites={m:s['aggregate'] for m,s in summaries.items()},fresh_D=True,planned_native_cells=66)
    save(dest/'combined_dataset_equal.json',combined)
    fields=['suite','case_id','method','family','original_split','IO','hit','miss','penalty','penalty_miss','physical','D','cost','score','raw_unclipped_points','ratio_to_Naive']
    with (dest/'per_case.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for mode,s in summaries.items():
            for row in s['per_case']:writer.writerow(dict(suite=mode,**row))
    lines=['# One-shot BUILD comparison','','PROVISIONAL: formal only with ../publication.json binding this report hash.','', 'Independent Naive/Full/BuildBestFit ×(dyna12+stat10)=66 cells, one repeat and fresh D. Native stdout Total_Score is authoritative C. Suites are separate; no old84 primary or pooled22 claim.','', '|Suite|Method|Score|raw points|Mean C/Naive|Physical/Full mean|D total us|', '|---|---|---:|---:|---:|---:|---:|']
    for mode,s in summaries.items():
        for row in s['aggregate']:lines.append('|{}|{}|{:.9f}|{:.9f}|{:.9f}|{:.9f}|{:.2f}|'.format(mode,row['method'],row['average_score'],row['mean_raw_unclipped_points'],row['ratio_to_Naive']['mean'],row['references']['Full']['physical_ratio']['mean'],row['D_total_us']))
    lines+=['','All per-case metrics, negative cases, exact new costs, physical/D decomposition and nearest-rank P50/P90/worst ratios are retained in JSON/CSV. Historical controls only verify identical-input IO/hit/miss and never supply D. Local synthetic, observed datasets; one timing measurement is descriptive. No retry, tuning or automatic promotion.']
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
