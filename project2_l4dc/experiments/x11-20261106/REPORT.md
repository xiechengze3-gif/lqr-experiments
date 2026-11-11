# X11 CE rectangular sweeps

352 new physical paths,11 unique cells,8systems x4seeds,184729600transitions; 0GraceSU. Square48/16 reused from verified local sources; no resampling. All1760 raw fit archive hashes checked. Every arm/N stability denominator32.

| n | m | Dense N at gap.01 | Rank2 N at gap.01 | Sample ratio |
|---:|---:|---:|---:|---:|
|16|16|9288.13|2575.01|3.607|
|24|16|16510.66|4073.75|4.053|
|32|16|19799.06|5410.86|3.659|
|48|4|10528.03|7340.42|1.434|
|48|6|14269.89|7471.22|1.910|
|48|8|18035.36|8224.73|2.193|
|48|12|24241.19|7798.19|3.109|
|48|16|29879.36|7662.13|3.900|
|48|24|43580.57|7866.22|5.540|
|48|32|56295.87|8176.79|6.885|
|48|48|82250.15|8116.91|10.133|
|64|16|42053.81|11142.45|3.774|
|96|16|63472.77|16212.03|3.915|

New arm-prefix failure records: 0/3520. See stability_by_N.csv for each cell and N; censoring_flags.csv for every arm. Crossing is the original median32 gap/log-log first downcross, no extrapolation. Square48 original paper crossings reproduce from its rounded report-transcribed gap CSV; raw full-precision crosses differ by 0.3000 dense and 0.02047 rank2 samples. Square16 reproduces directly from full-precision X10a records. Original source values retained in merged rows; all new rows use full precision with the same crossing arithmetic. See legacy_rounding_audit.csv. Report-v1 stopped on this provenance check and is preserved; no trajectory rerun. Paired ratio instead aggregates within-seed pairs, then per-system medians. These distinct statistics are labeled.

Both figures are saved-record descriptive comparisons. All failures retained; no theorem verification or epsilon-success-probability claim. Source/caches/temp/output on E; one BLAS thread each, four local workers. Old results and paper untouched.

Descriptive interpretation: fixing n48, the new m4..32 cells increase dense requiredN from10528 to56296 while rank2 stays7340..8225; sample-cost ratios rise1.43..6.89. The reused square48 endpoint has ratio10.13. Fixing m16, n16..96 yields ratios3.61..4.05 (n16 reused). Thus the gain grows strongly with redundant input dimension in this family, and stays approximately constant when only state dimension increases. This is an empirical comparison, not proof of dimension scaling.

Final figures: figures-v3/sample_cost.png and paired_gap_ratios.png, with SVG versions and saved-CSV-only render receipt. Original report-v2 figures and failed report-v1 remain immutable.
