# X7 figure inspection

All five figures-v1 PNGs were opened with view_image and visually inspected after rendering. The matching SVGs share the same Matplotlib figure state. Panel titles, row/axis labels, legends, color bars and captions are visible; no clipped scientific values or overlapping legends were observed.

- fixed_orders: every registered fixed order including dense; post hoc order boxed; both spectra; zero failure counts and burn-in convention disclosed.
- adaptive_gaps: both adaptive rules, both sensitivities, dense and clearly labeled group post hoc diagnostic; IQR shading; all six budgets retained. Polynomial losses and n24 geometric high-budget paper-rule loss remain visible.
- adaptive_orders: full rank and order-zero outcomes visible; changing order and polynomial return to dense visible; no monotonicity imposed.
- paired_ratios: every non-dense arm, with exact annotated paired medians. Color clipping is explicitly stated; unfavorable ratios below one are retained. CSVs retain the complete CIs and eligibility counts.
- log_slopes: every registered arm and both windows; point estimates and saved CI segments; unidentified bootstrap counts shown. Both metrics and all intervals remain in log_slopes.csv even though this figure displays relative gaps.

The plot source reads only saved CSVs and verifies all nine hashes. No new statistical analysis or model calculation was performed locally. Output cache and temporary paths are explicitly under this E-drive experiment folder. These checks concern presentation; compute-node numerical audit proofs remain separate.
