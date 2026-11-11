Scope: X3 CE adaptive-order metadata correction, saved data only. The old aggregate `k` field on adaptive rows retained the first observed order; it must not be read as a fixed order for all32 outputs. Original bytes are preserved.

New `X3/report-ce-failure-detail-v5/` provides1296 full method/budget cells and1554 actual-selected-order subgroups;119 cells have varying selected orders. Every full cell still has32 outputs; each adaptive-order subgroup shows its selected count beside the full32 denominator. All gap/IQR, failure totals and figures remain unchanged.

The category is now `learning_method`, not a label suggesting every selected k>=1. Fixed-k0 diagnostic failures3456 remain separate; adaptive methods selecting k0 remain their own learning failures. Total5747, learning2291, unchanged. The v4 adaptive-explanation table already used per-output k and remains correct. README/REPORT give the exact supersession and hashes. Zero model fitting/evaluation/learning runs.
