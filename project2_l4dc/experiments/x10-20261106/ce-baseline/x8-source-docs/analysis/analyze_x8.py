"""Post hoc analysis of X8 (see PROTOCOL.md and PROTOCOL_AMENDMENT.md).
Reads x8_b_raw.csv, x8_c_raw.csv; writes x8_medians.csv and x8_sample_cost.csv.
Sample cost: regression transitions N at which the median ABSOLUTE gap over the 32 runs
reaches eps (log-log interpolation between adjacent grid points; first downward crossing;
no extrapolation; unstable outputs count as +inf). 95% CI: bootstrap over the 8 systems
(all 4 seeds of a resampled system kept), 2000 draws, seed 0."""
import sys, numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).resolve().parent.parent
EPS = [0.01, 0.005]

def load():
    b = pd.read_csv(H / 'x8_b_raw.csv'); b['family'] = 'exact'
    c = pd.read_csv(H / 'x8_c_raw.csv'); c['family'] = 'geometric'
    d = pd.concat([b, c]); d['order'] = d.order.astype(str)
    d['abs_gap'] = d.rel_gap * d.g0
    return d

def cost(N, y, e):
    if y[0] <= e: return N[0]            # left-censored at the first grid point
    for i in range(1, len(y)):
        if np.isfinite(y[i - 1]) and y[i - 1] > e >= y[i]:
            t = (np.log(e) - np.log(y[i - 1])) / (np.log(y[i]) - np.log(y[i - 1]))
            return float(np.exp(np.log(N[i - 1]) + t * (np.log(N[i]) - np.log(N[i - 1]))))
    return np.inf                         # right-censored

def k_eps(config, e):
    if not config.startswith('rho'): return int(config[1:])
    rho = float(config[3:]); s = rho ** np.arange(48)
    tail = np.array([np.sum(s[k:] ** 2) for k in range(49)])
    return max(int(np.argmax(tail <= e)), 1)

def main():
    d = load(); rng = np.random.default_rng(0)
    med = d.groupby(['family', 'config', 'order', 'N']).agg(
        median_abs_gap=('abs_gap', 'median'), median_rel_gap=('rel_gap', 'median'),
        n_unstable=('rel_gap', lambda x: int(np.sum(~np.isfinite(x)))), runs=('rel_gap', 'size')).reset_index()
    med.to_csv(H / 'analysis' / 'x8_medians.csv', index=False)
    rows = []
    for (fam, cfg), g in d.groupby(['family', 'config']):
        g0 = g.groupby('system').g0.first()
        for e in EPS:
            k = k_eps(cfg, e); order = 'dense' if (fam == 'geometric' and k >= 48) else str(k)
            for arm, o in [('truncated', order), ('dense', 'dense')]:
                s = g[g.order == o]
                piv = s.pivot_table(index=['system', 'seed'], columns='N', values='abs_gap')
                Ns = np.array(piv.columns, float); arr = piv.values
                est = cost(Ns, np.median(arr, 0), e)
                systems = piv.index.get_level_values(0).values; ids = np.unique(systems)
                boots = []
                for _ in range(2000):
                    pick = rng.choice(ids, len(ids), replace=True)
                    rr = np.concatenate([arr[systems == i] for i in pick])
                    boots.append(cost(Ns, np.median(rr, 0), e))
                boots = np.array(boots)
                rows.append(dict(family=fam, config=cfg, eps=e, k=k, arm=arm, order=o, N_req=est,
                                 ci_low=np.quantile(boots, .025), ci_high=np.quantile(boots, .975),
                                 censored_draws=int(np.sum(~np.isfinite(boots))),
                                 g0_median=float(g0.median()), n_unstable=int(np.sum(~np.isfinite(s.abs_gap)))))
    out = pd.DataFrame(rows); out.to_csv(H / 'analysis' / 'x8_sample_cost.csv', index=False)
    print(out.to_string())

if __name__ == "__main__" and len(sys.argv) == 1:
    main()

def registered():
    """Registered analysis of PROTOCOL.md: relative targets eps_rel in {0.05, 0.02} (no bootstrap)."""
    d = load(); rows = []
    for (fam, cfg), g in d.groupby(['family', 'config']):
        g0 = g.groupby('system').g0.first().median()
        for er in [0.05, 0.02]:
            k = k_eps(cfg, er * g0) if fam == 'geometric' else int(cfg[1:])
            order = 'dense' if (fam == 'geometric' and k >= 48) else str(k)
            for arm, o in [('truncated', order), ('dense', 'dense')]:
                piv = g[g.order == o].pivot_table(index=['system', 'seed'], columns='N', values='rel_gap')
                rows.append(dict(family=fam, config=cfg, eps_rel=er, k=k, arm=arm, order=o,
                                 N_req=cost(np.array(piv.columns, float), np.median(piv.values, 0), er), g0_median=g0))
    out = pd.DataFrame(rows); out.to_csv(H / 'analysis' / 'x8_sample_cost_registered.csv', index=False)
    print(out.to_string())

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'registered':
    registered()
