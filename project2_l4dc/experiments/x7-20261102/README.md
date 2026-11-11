# X7 delivery

CE with full-rank decaying actuation spectra, fixed system certificates, and growing retained order. Start with SCIENCE_REPORT.md, RESULT_TABLES.md and figures-v1/fixed_orders.png. All nine frozen compute-node CSVs are directly in this directory at the requested shallow path. summary-verification.json records their source hashes. No paper tex or previous result was edited.

The geometric spectrum supports useful truncation; the polynomial spectrum returns to dense as N grows. Paper C5=2.569 and split thresholds are reported with unfavorable comparisons retained. The best fixed order is a post hoc group diagnostic, not an available learner.

Regenerate presentation into a NEW directory with the existing E-drive Python:

```powershell
& 'E:\anaconda\python.exe' -B 'E:\ChatGPT\Projects\LQR_experiments\project2_l4dc\experiments\x7-20261102\plot_saved_ce.py' --out 'E:\ChatGPT\Projects\LQR_experiments\project2_l4dc\experiments\x7-20261102\figures-regenerated-v1'
```

The plotter verifies all CSV hashes and uses E-drive cache/temp locations. It imports no experiment engine and runs no statistical refits. Do not rerun publish_saved_ce.py into this delivered folder: it deliberately rejects overwriting frozen published files. Scientific code and numeric audits are compute-node only.

Five figure pairs in figures-v1: fixed_orders (all fixed orders), adaptive_gaps (all adaptive/sensitivity curves), adaptive_orders (chosen orders and zero-order disclosure), paired_ratios (every non-dense arm), log_slopes (all registered arms). Each is PNG plus vector SVG. PLOT_MANIFEST.json records hashes. Labels and error treatment are described in SCIENCE_REPORT.md and the CSVs.

Formal and report files are in delivery-formal-v1 and delivery-report-v1. Their download archives and per-file manifests are in downloads-v1; adjacent *.verified.json receipts confirm pre-extraction archive/member verification. The formal archive includes resource/model provenance. All scientific source/config hashes remain those accepted before formal execution. The separate accounting snapshot follows all completed jobs; archived metadata/logs were captured during packing.

PROTOCOL.md, prepared-formal-v1/formal-config.json, RESOURCE_COMPLETE_v1.json, FORMAL_COMPLETE_v1.json, DIAGNOSTICS_COMPLETE_v3.json, summary-verification.json and DELIVERY_CHECK_v1.json provide the review chain. DELIVERY_MANIFEST_v1.json covers the shallow delivery and figures and points to sealed raw/report manifests.
