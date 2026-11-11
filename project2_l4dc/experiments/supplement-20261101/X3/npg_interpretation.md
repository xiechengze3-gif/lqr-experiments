Final interpretation and selection implications, based on the complete formal grid:

- **No clear total-gap advantage for truncated NPG in this grid.** Among36 predeclared
  dense/k gap comparisons,31 bootstrap95% intervals lie wholly below1,5 include1,
  and none lies wholly above1. All pairs are finite32/32; this result is not caused
  by excluding unstable paths. Smooth and flat spectra select dense k12 at every
  budget by the absolute-gap median. The flat control strongly penalizes truncation.
- **The two-level spectrum gives only a weak low-budget tradeoff.** Its absolute-gap
  envelope is k4 -> k12 -> k12; the relative-gap envelope is k6 -> k12 -> k12.
  At multiplier1, the k4 absolute median is.130425 versus dense.140630, but the
  paired ratio1.02154 [.942661,1.14822] does not establish an advantage. At the
  higher budgets all four truncated-arm gap-ratio intervals lie below1.
  Do not write a universal increasing-order law: smooth and flat are constant12.
- **The requested last-stage diagnostic improves while endpoint cost can worsen.**
  On the two-level spectrum, k2 own-arm last Frobenius-error medians are
  1.70801 /.740596 /.376743 versus dense2.14140 /1.10263 /.532519.
  The own-arm paired error ratios1.34675 /1.39405 /1.50404 all have CIs above1.
  At the same dense policy and raw estimate, offline k2 error ratios are
  1.40634 [1.37403,1.44274],1.46098 [1.38465,1.51105],
  1.52297 [1.47541,1.54158], also favoring truncation.
  Nevertheless actual endpoint dense/k2 gap ratios are
  .829825 [.692967,1.09804],.586978 [.550807,.786260],
  .443481 [.417849,.607949]. Lower last-stage unweighted Frobenius error alone
  therefore does not imply lower terminal control cost.

These are full-rank plants with nonzero discarded directions. Truncation bias,
policy-dependent targets, cost weighting and the entire optimization history can
all matter. This diagnostic does not isolate their causal contributions or certify
the theorem's sufficient small-error constants. It does not establish that poor
estimated-subspace alignment is the unique cause. Own-arm estimates belong to
different actual K63; the common-dense-policy branch is the comparison with a
shared policy and shared raw estimate, and has no counterfactual endpoint.

For manuscript selection, keep the NPG result as a negative/control and mechanism
result, or explicitly describe it that way in the main text. It is unsuitable as
positive evidence of a general total-gap or sample-complexity gain from truncation.
CE remains the stronger main positive evidence. Preserve the weak low-budget cell,
flat-spectrum control, all failure denominators and all36 intervals. Do not tune
eta, T, budgets or ranks after seeing this result; no additional experiment was run.
