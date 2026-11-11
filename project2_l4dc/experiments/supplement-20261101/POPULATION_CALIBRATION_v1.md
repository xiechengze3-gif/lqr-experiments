# X2/X3 NPG population calibration supplement (before finite-data pilots)

This is a shared, zero-training-transition Slurm pilot, not a formal run and not
evidence of finite-sample learning. Source `population_suite.py` is frozen in the
new auxiliary release manifest before execution.

X2 uses n12/24/48,r2,nonzero-null initializers from its protocol; formal systems
201–208 provide the arm-independent per-n max-initial-P certificate, pilot
systems9003/9004 alone determine optimization progress. X3 uses n12 across its
smooth/two-level/flat spectra, formal systems301–308 for the common initial-P
bound, pilot9005/9006 alone for population progress.

For each dimension, eta=1/(1+2*p0_bar), B norm1 and R=I. Check exact-gradient
population NPG at T64/96/128/192/256/384/512/768; choose the first T with every
pilot plant stable and relative gap<=.05. Preserve nonqualification and any
instability, with no seed replacement or step-size change. These are the same
R1/R2 principles Claude explicitly accepted for X1. No formal learning output
or policy performance is read for calibration. Formal initialization certificates
are permitted side information, not an objective-tuned initializer.

The resolved values, finite-data nd/a_t² schedule and dense-only batch calibration
remain subject to the corresponding experiment's explicit formal acceptance.
One shared single-core2GiB job,max10min,upper0.166667SU, counted once globally.
The60-minute exception remains disabled under the direct user's requirement.
