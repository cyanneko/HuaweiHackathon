# One-shot BUILD comparison

PROVISIONAL: formal only with ../publication.json binding this report hash.

Independent Naive/Full/BuildBestFit ×(dyna12+stat10)=66 cells, one repeat and fresh D. Native stdout Total_Score is authoritative C. Suites are separate; no old84 primary or pooled22 claim.

|Suite|Method|Score|raw points|Mean C/Naive|Physical/Full mean|D total us|
|---|---|---:|---:|---:|---:|---:|
|dyna|Naive|0.000000000|0.000000000|1.000000000|3.315025879|27838553.03|
|dyna|Full|4.455852989|4.455852989|0.554414701|1.000000000|29790738.94|
|dyna|BuildBestFit|4.454908848|4.454908848|0.554509115|1.000132603|32355095.79|
|stat|Naive|0.000000000|0.000000000|1.000000000|1.701697924|11423576.43|
|stat|Full|3.439749405|3.439749405|0.656025060|1.000000000|11138208.88|
|stat|BuildBestFit|3.445074880|3.445074880|0.655492512|0.999213465|11209250.46|

All per-case metrics, negative cases, exact new costs, physical/D decomposition and nearest-rank P50/P90/worst ratios are retained in JSON/CSV. Historical controls only verify identical-input IO/hit/miss and never supply D. Local synthetic, observed datasets; one timing measurement is descriptive. No retry, tuning or automatic promotion.
