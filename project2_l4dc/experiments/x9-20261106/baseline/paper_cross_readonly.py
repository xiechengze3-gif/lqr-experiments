# Read-only source excerpt, not imported/executed locally.
def cross(N, y, e):
    """Transitions at which the curve y(N) first falls to e (log-log interpolation); nan if never, -N0 if at start."""
    N = np.asarray(N, float); y = np.asarray(y, float)
    if np.isfinite(y[0]) and y[0] <= e: return -N[0]
    for i in range(1, len(y)):
        if np.isfinite(y[i - 1]) and y[i - 1] > e >= y[i]:
            t = (np.log(e) - np.log(y[i - 1])) / (np.log(y[i]) - np.log(y[i - 1]))
            return float(np.exp(np.log(N[i - 1]) + t * (np.log(N[i]) - np.log(N[i - 1]))))
    return np.nan
