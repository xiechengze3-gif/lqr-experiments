# X12 saved-data report

Descriptive extension of the accepted X6b/X10b experiments to n=m=60. No theorem verification or epsilon/probability guarantee.

Family S, Q=R=W=I, exact rank B=2, retained rank k=2, K0=0, eta=.2, nu=1, H=16. NPG16/PI8 updates; 16 pulse burn blocks and one baseline block each update; fixed growing integer schedules. Every arm/rung has its own continuous state and paired external randomness. These are the frozen observation-only Stein NPG and PI learners; PI retains its registered joint compression and PSD regularization. No critic/LSTD, oracle input, line search, gain clipping, recovery or adaptive rank is introduced.

Pilot K0-only calibration selected N_cal=2097152 from the complete registered grid. This selection does not certify all-stage estimation errors or the sufficient theoretical constants. Instability at these empirical budgets is not a contradiction of the theorem conditional on its sufficient sample bounds. Here N_cal is the per-stage Stein block base; the legacy derived-CSV column N_cal instead stores the full-rung primitive transition total per arm, preserving the original schema. Every formal configuration was fixed before observations: 8 systems301..308 x4 seeds1701..1704, nine rungs1/256..1, two algorithms and both arms. All576paired paths/1152arms and193644738560formal transitions are retained.

Instability is absorbing and consumes its remaining registered budget under K0 padding. All gap medians/IQR use the full32 denominator with failures at infinity. Failure counts/rates appear at every plotted budget and in CSV. Both paired-ratio definitions, 5000 system-cluster bootstrap draws, undefined bootstrap mass, and all attainment/censoring diagnostics follow the unchanged original analyzer. Saved-stage estimator arrays, updates, padding counts and checkpoint hashes are audited on compute nodes.

summary.csv under new-n60 contains36new rows in the exact X6b schema. summary_merged_nine_rungs.csv contains180rows with the accepted144row X10b table as an exact byte prefix. The original8derived saving-factor rows, failures and per-cell counts are also exact prefixes of their merged copies. Old results are reused without simulation, bootstrap or reanalysis.

|algorithm|rung|M per arm|dense gap median|truncated gap median|dense stable|truncated stable|paired ratio [95% CI]|
|---|---:|---:|---:|---:|---:|---:|---|
|NPG|0.00390625|2964976|∞|11.323|0/32|32/32|∞ [∞, ∞]|
|NPG|0.0078125|5925440|∞|4.1919|0/32|32/32|∞ [∞, ∞]|
|NPG|0.015625|11846384|42.725|2.0081|32/32|32/32|20.903 [18.918, 24.856]|
|NPG|0.03125|23688352|9.0314|1.0321|32/32|32/32|8.7541 [8.5699, 8.8614]|
|NPG|0.0625|47372272|3.8944|0.54791|32/32|32/32|6.9792 [6.915, 7.1061]|
|NPG|0.125|94740080|1.7972|0.2944|32/32|32/32|6.067 [5.8591, 6.2745]|
|NPG|0.25|189475712|0.88096|0.15271|32/32|32/32|5.7852 [5.6485, 6.0268]|
|NPG|0.5|378946928|0.43322|0.066365|32/32|32/32|6.5672 [6.0134, 6.7923]|
|NPG|1.0|757889376|0.21296|0.026108|32/32|32/32|8.1957 [8.0406, 8.5903]|
|PI|0.00390625|2964976|∞|1.0627|0/32|32/32|∞ [∞, ∞]|
|PI|0.0078125|5925440|∞|0.81676|0/32|32/32|∞ [∞, ∞]|
|PI|0.015625|11846384|∞|0.49126|0/32|32/32|∞ [∞, ∞]|
|PI|0.03125|23688352|∞|0.26446|0/32|32/32|∞ [∞, ∞]|
|PI|0.0625|47372272|∞|0.13321|0/32|32/32|∞ [∞, ∞]|
|PI|0.125|94740080|4.0305|0.062552|32/32|32/32|63.708 [61.625, 65.779]|
|PI|0.25|189475712|1.8277|0.033232|32/32|32/32|54.239 [53.24, 57.213]|
|PI|0.5|378946928|0.89844|0.016551|32/32|32/32|54.969 [52.199, 59.209]|
|PI|1.0|757889376|0.45318|0.0083847|32/32|32/32|54.123 [49.386, 57.027]|

|algorithm|n60 saving factor|left censored|right censored|unbracketed|
|---|---:|---|---|---|
|NPG|5.6828|False|False|False|
|PI|58.453|False|False|False|

Factors use the verbatim paper cross function: first log-log crossing of the truncated full32 median curve with the dense full-rung median. No smoothing or extrapolation. Censoring and unidentified targets remain explicit.

The frozen cost gate uses max(measured n60 pilot body,historical larger-dimension floor), ceil((1.20*body+30)/60) task limits, all pilots, model-only prep and8SU report reserve. Actual-spend forecast<=230SU; requested upper<=300SU; total own concurrency<=64. Completed Slurm elapsed, forecast, requested reservations and AMS settlements are distinct; overlapping AMS and Slurm charges are never added.

No old result, release, paper source or TeX is edited. Full raw outputs, models, RNG receipts, sources and ledgers accompany the report.
