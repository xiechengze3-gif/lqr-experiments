# X7 resource PILOT report

All four allocations20375552_0..3 COMPLETED;effective billing cores1 each.
No gap,stability,rank or control-performance readout/selection was performed.
Resource trajectories16+4unchangedce_run references;5908480pilot transitions.
All32 deterministic formal model inputs were frozen,zero formal observations.

|case|worst complete path sec|peak process MiB|equivalence checks|max policy relative error|
|---|---:|---:|---:|---:|
|n24-geometric|12.220402|129.320|84|0|
|n24-polynomial|12.400084|127.582|84|0|
|n48-geometric|14.642719|137.871|96|0|
|n48-polynomial|13.625448|135.906|96|0|

Full/half OLS,final state/RNG and common fields bitwise PASS;policies error0.
Resourceproof SHA db8a365716e0a616cc6a9f390ccae4a8b2e872e3d34d62d20d07d85a8ee47ed5.
Sumworst52.888653010s;ceil((1.3*sum+60)/60)=3min.
Measured formal plan32bundles×1CPU/2GiB/3min=1.6SU,concurrency8.
Peak141180KiB=137.871MiB,headroom93.268%,exceeding20%.
Formal configSHA 22711b80c3ff8c353d255eeb6d5fd314a2c78decf84864dcb3a037b1892db09d;formal planSHA 17b93a6a012562fa57c1d14360de66c7268669b8c3bdfcd8669e00a1da7c6b5a.

CurrentX7requested1/15SU;allpilotcompletedSlurm0.078333333SU,
AMSsettled0 at2026-11-02T23:31:21Z(separate overlapping views,notadded).
Prospectiveformal1.6+REPORTreserve2 -> cumulative upper4.6/15SU.
The17:30 review explicitly pre-accepts FORMAL if<=12SU and RSSheadroom>=20%;
both hold. Thereforeafterthispublication,submitwithoutanotheracceptance.
prepare_formal.py'sgenericAWAITINGstatuslabelpredates thatconditionalreview;
the actual gate is recorded inFORMAL_CONDITIONS_MET.json.
No scientific/config tuning,no sourcehash change,no retriesorgridcuts.
