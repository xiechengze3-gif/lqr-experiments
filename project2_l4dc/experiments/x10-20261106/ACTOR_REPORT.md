# X10b saved-data report

Descriptive densification of X6b. The five added rungs and all systems/seeds were fixed before the pilot. This report makes no new theorem verification or epsilon/probability claim.

Family S; n=m in 24,36,48,72; exact actuation rank 2; Q=R=W=I; K0=0; eta=.2, nu=1, H=16; 16 pulse burn blocks and one baseline block per stage; NPG16/PI8 updates. Original models, integer stage growth, N_cal, pairing and observation-only learners are preserved. One continuous trajectory per arm/rung. Instability is absorbing; remaining transitions are consumed by the registered K0 padding.

The original four-rung summary bytes are the exact prefix of summary_merged_nine_rungs.csv. The 80 new summary rows follow the unchanged original statistics and system-bootstrap draws. Only the report coverage assertion was generalized from four to the five registered new rungs; COVERAGE_SOURCE_PROOF_v1.json verifies the reversible one-line change and literal identity of all other functions.

Every gap median/IQR uses the full denominator 32, with failures at infinity. Both paired-ratio definitions and bootstrap undefined mass are retained in the summary. Figures show failure counts in left-to-right rung order; failure_counts_by_cell.csv gives counts and rates; failures.csv contains every saved baseline and new endpoint failure.

|n|algorithm|rung|M per arm|dense gap median|truncated gap median|dense stable|truncated stable|paired ratio [95% CI]|
|---:|---|---:|---:|---:|---:|---:|---:|---|
|24|NPG|0.00390625|744608|∞|30.652|0/32|19/32|∞ [∞, ∞]|
|24|NPG|0.0078125|1484704|∞|2.8941|0/32|32/32|∞ [∞, ∞]|
|24|NPG|0.015625|2964976|6.0286|1.2807|32/32|32/32|4.5094 [4.3719, 4.8621]|
|24|NPG|0.03125|5925440|2.2488|0.61789|32/32|32/32|3.5852 [3.3838, 3.7141]|
|24|NPG|0.0625|11846384|1.0011|0.31175|32/32|32/32|3.1583 [3.0573, 3.2365]|
|24|NPG|0.125|23688352|0.48241|0.16604|32/32|32/32|2.8935 [2.7209, 3.1954]|
|24|NPG|0.25|47372272|0.23079|0.083244|32/32|32/32|2.8455 [2.7034, 2.9718]|
|24|NPG|0.5|94740080|0.11471|0.038373|32/32|32/32|3.1018 [2.8656, 3.2078]|
|24|NPG|1.0|189475712|0.057937|0.014875|32/32|32/32|3.9752 [3.6421, 4.4018]|
|24|PI|0.00390625|744608|∞|1.0399|0/32|32/32|∞ [∞, ∞]|
|24|PI|0.0078125|1484704|∞|0.69468|0/32|32/32|∞ [∞, ∞]|
|24|PI|0.015625|2964976|∞|0.36278|0/32|32/32|∞ [∞, ∞]|
|24|PI|0.03125|5925440|∞|0.17571|0/32|32/32|∞ [∞, ∞]|
|24|PI|0.0625|11846384|∞|0.087148|13/32|32/32|∞ [844.38, ∞]|
|24|PI|0.125|23688352|0.97843|0.047455|32/32|32/32|21.128 [19.676, 22.104]|
|24|PI|0.25|47372272|0.49154|0.023854|32/32|32/32|21.101 [19.914, 22.259]|
|24|PI|0.5|94740080|0.23572|0.011532|32/32|32/32|20.954 [19.764, 21.766]|
|24|PI|1.0|189475712|0.12375|0.0057515|32/32|32/32|21.614 [20.018, 23.195]|
|36|NPG|0.00390625|1484704|∞|8.6569|0/32|32/32|∞ [∞, ∞]|
|36|NPG|0.0078125|2964976|∞|3.0549|0/32|32/32|∞ [∞, ∞]|
|36|NPG|0.015625|5925440|9.6059|1.4784|32/32|32/32|6.9204 [6.4865, 7.4056]|
|36|NPG|0.03125|11846384|3.584|0.72148|32/32|32/32|4.9054 [4.8353, 5.0669]|
|36|NPG|0.0625|23688352|1.5891|0.38623|32/32|32/32|4.1834 [4.0323, 4.3384]|
|36|NPG|0.125|47372272|0.75737|0.19182|32/32|32/32|3.9199 [3.7971, 4.0781]|
|36|NPG|0.25|94740080|0.37082|0.091582|32/32|32/32|3.9383 [3.8074, 4.1677]|
|36|NPG|0.5|189475712|0.18749|0.041998|32/32|32/32|4.3867 [4.2615, 4.6536]|
|36|NPG|1.0|378946928|0.092531|0.016134|32/32|32/32|5.6722 [5.5687, 5.9057]|
|36|PI|0.00390625|1484704|∞|1.0502|0/32|32/32|∞ [∞, ∞]|
|36|PI|0.0078125|2964976|∞|0.67076|0/32|32/32|∞ [∞, ∞]|
|36|PI|0.015625|5925440|∞|0.37941|0/32|32/32|∞ [∞, ∞]|
|36|PI|0.03125|11846384|∞|0.19147|0/32|32/32|∞ [∞, ∞]|
|36|PI|0.0625|23688352|∞|0.097408|5/32|32/32|∞ [∞, ∞]|
|36|PI|0.125|47372272|1.6228|0.051036|32/32|32/32|32.017 [31.165, 34.318]|
|36|PI|0.25|94740080|0.77932|0.026398|32/32|32/32|31.183 [28.106, 33.439]|
|36|PI|0.5|189475712|0.38618|0.012639|32/32|32/32|30.609 [29.361, 31.762]|
|36|PI|1.0|378946928|0.19064|0.0063892|32/32|32/32|29.906 [29.661, 30.644]|
|48|NPG|0.00390625|2964976|∞|5.8828|0/32|32/32|∞ [∞, ∞]|
|48|NPG|0.0078125|5925440|∞|2.5539|0/32|32/32|∞ [∞, ∞]|
|48|NPG|0.015625|11846384|10.539|1.2529|32/32|32/32|8.4253 [8.2078, 8.5786]|
|48|NPG|0.03125|23688352|4.1452|0.66774|32/32|32/32|6.2437 [6.0429, 6.364]|
|48|NPG|0.0625|47372272|1.8928|0.35446|32/32|32/32|5.325 [5.1612, 5.4791]|
|48|NPG|0.125|94740080|0.90412|0.17838|32/32|32/32|5.032 [4.8425, 5.191]|
|48|NPG|0.25|189475712|0.44234|0.086536|32/32|32/32|5.022 [4.8561, 5.2975]|
|48|NPG|0.5|378946928|0.22038|0.0361|32/32|32/32|6.1592 [5.7542, 6.4988]|
|48|NPG|1.0|757889376|0.10807|0.01413|32/32|32/32|7.8918 [7.7273, 8.0759]|
|48|PI|0.00390625|2964976|∞|0.89321|0/32|32/32|∞ [∞, ∞]|
|48|PI|0.0078125|5925440|∞|0.65397|0/32|32/32|∞ [∞, ∞]|
|48|PI|0.015625|11846384|∞|0.33535|0/32|32/32|∞ [∞, ∞]|
|48|PI|0.03125|23688352|∞|0.1726|0/32|32/32|∞ [∞, ∞]|
|48|PI|0.0625|47372272|17.312|0.081346|30/32|32/32|204.67 [127.65, 595.4]|
|48|PI|0.125|94740080|1.8962|0.042143|32/32|32/32|44.09 [42.948, 46.037]|
|48|PI|0.25|189475712|0.92547|0.021002|32/32|32/32|43.639 [42.701, 46.913]|
|48|PI|0.5|378946928|0.46199|0.010657|32/32|32/32|43.81 [43.015, 46.18]|
|48|PI|1.0|757889376|0.23237|0.0052211|32/32|32/32|44.308 [40.916, 48.054]|
|72|NPG|0.00390625|5925440|∞|6.3725|0/32|32/32|∞ [∞, ∞]|
|72|NPG|0.0078125|11846384|∞|2.9191|0/32|32/32|∞ [∞, ∞]|
|72|NPG|0.015625|23688352|19.994|1.4858|32/32|32/32|13.66 [13.369, 13.807]|
|72|NPG|0.03125|47372272|7.1653|0.80703|32/32|32/32|8.9179 [8.7301, 9.0835]|
|72|NPG|0.0625|94740080|3.26|0.43786|32/32|32/32|7.5554 [7.2844, 7.7161]|
|72|NPG|0.125|189475712|1.5604|0.226|32/32|32/32|6.917 [6.6663, 7.1538]|
|72|NPG|0.25|378946928|0.76796|0.10783|32/32|32/32|6.969 [6.8644, 7.2443]|
|72|NPG|0.5|757889376|0.37735|0.042687|32/32|32/32|8.8822 [8.6568, 9.0541]|
|72|NPG|1.0|1515774320|0.18674|0.016513|32/32|32/32|11.324 [10.964, 11.492]|
|72|PI|0.00390625|5925440|∞|0.97562|0/32|32/32|∞ [∞, ∞]|
|72|PI|0.0078125|11846384|∞|0.67835|0/32|32/32|∞ [∞, ∞]|
|72|PI|0.015625|23688352|∞|0.37731|0/32|32/32|∞ [∞, ∞]|
|72|PI|0.03125|47372272|∞|0.19869|0/32|32/32|∞ [∞, ∞]|
|72|PI|0.0625|94740080|∞|0.092661|10/32|32/32|∞ [3.4932e+05, ∞]|
|72|PI|0.125|189475712|3.2723|0.048524|32/32|32/32|67.369 [67.023, 68.591]|
|72|PI|0.25|378946928|1.5849|0.024315|32/32|32/32|65.819 [63.683, 67.103]|
|72|PI|0.5|757889376|0.79064|0.01204|32/32|32/32|66.029 [63.006, 67.866]|
|72|PI|1.0|1515774320|0.40034|0.0061157|32/32|32/32|65.982 [63.7, 70.186]|

|n|algorithm|nine-rung saving factor|four-rung factor|left censored|right censored|unbracketed|
|---:|---|---:|---:|---|---|---|
|24|NPG|2.8918|2.9877|False|False|False|
|36|NPG|4.0387|4.0398|False|False|False|
|48|NPG|4.9493|4.9767|False|False|False|
|72|NPG|6.6904|6.8862|False|False|False|
|24|PI|22.616|22.483|False|False|False|
|36|PI|31.846|31.713|False|False|False|
|48|PI|43.633|44.683|False|False|False|
|72|PI|68.627|63.988|False|False|False|

Saving factors use the verbatim paper cross function: first log-log crossing of the truncated full-population median curve with the dense full-rung median. No smoothing or extrapolation. Left censoring is an observed bound; missing targets or finite brackets remain flagged. The recomputed original four-rung values match every field of the captured paper CSV.

Budget/provenance files distinguish predicted actual spend, requested allocation upper bounds and completed Slurm elapsed cost. AMS settlement overlaps Slurm and is never added to it. The clarified gates are actual forecast <=160 SU and requested upper <=200 SU, including pilot and report.

The original pilot failed only because old remote reference arrays were missing (57s); its two timing jobs were dependency-canceled (0s). The explicitly authorized correction reused completed NPG without resampling and ran only PI replay plus the original untouched timing jobs. All strict record/array/RNG/count checks passed, with no changed learning source or tolerance. Both resource-v1 and resource-v2, original failures and cumulative requested/spent costs are retained in the full delivery.

Formal and report consume packaged model/old CSV bytes verified against the local X6b-report-v1 delivery. No old remote X6b raw file is required. New complete-task outputs are copied incrementally to the E-drive delivery with file hashes; original sources/results are preserved.

No existing results, releases, paper source or TeX were edited.
