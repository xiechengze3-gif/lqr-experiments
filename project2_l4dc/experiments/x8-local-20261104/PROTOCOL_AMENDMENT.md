# X8 analysis amendment (post hoc, 2026-11-05, after all runs completed)

No run, system, seed, grid, or arm was changed. Only the reported target changes.

- Registered metric (PROTOCOL.md): relative gap g/g(K0) at eps_rel in {0.05, 0.02}.
  Its results are kept in analysis/x8_sample_cost_registered.csv and reported in Appendix H.
- Reason for the amendment: the median of g(K0) over the 8 systems grows with the rank of B,
  from 0.133 (rank 1) to 5.45 (rank 48), and from 0.161 (rho = 0.3) to 1.82 (rho = 0.95). A relative
  target therefore asks for a smaller absolute gap at small rank, and mixes the dependence on k with
  that of g(K0). The theorems of the paper bound the absolute gap g(K) <= (1 + C_3) eps.
- Primary metric used in the paper (post hoc): absolute gap g(K) at eps in {0.01, 0.005}; truncation
  order k = rank B in (b) and k = max{k_eps(B), 1} with k_eps(B) = min{k : tau_k^2 <= eps} in (c), computed
  from the spectrum only. Sample cost = first downward crossing of eps by the median curve over the 32
  runs, log-log interpolation, no extrapolation; 95% intervals: bootstrap over the 8 systems, 2000 draws.
- Script: analysis/analyze_x8.py (default: amended analysis; argument "registered": registered analysis).
