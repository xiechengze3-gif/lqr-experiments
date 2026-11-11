"""Batch the arithmetic of the SAME sequential pulse trajectory, not samples."""
import json
import time
import numpy as np
from dense_scaling import njit, nominal_chunk, pulse_chunk, pulse_moments, system, rng_for


@njit(cache=True)
def block_starts(fh, x, increments):
    starts = np.empty_like(increments)
    for j in range(len(increments)):
        starts[j] = x
        x = fh @ x + increments[j]
    return starts


def prepare(f, b, horizon):
    powers = [np.eye(len(f))]
    for _ in range(horizon):
        powers.append(powers[-1] @ f)
    return powers, powers[-2] @ b


def batched_chunk(f, b, cost, x, pulses, noises, prepared):
    count, horizon, n = noises.shape
    powers, impulse = prepared
    increments = pulses @ impulse.T
    for t in range(horizon):
        increments += noises[:, t] @ powers[horizon - t - 1].T
    # Cross-block states are still computed sequentially, with no resets.
    starts = block_starts(np.ascontiguousarray(powers[-1]), x, increments)
    states, values = starts.copy(), np.zeros(count)
    for t in range(horizon):
        states = states @ f.T + noises[:, t]
        if t == 0:
            states += pulses @ b.T
        values += np.einsum('ij,ij->i', states, states @ cost.T)
    return states[-1].copy(), starts, values


def collect(s, k, x, budgets, horizon, sigma, rng, burn=512):
    f = np.ascontiguousarray(s['A'] - s['B'] @ k)
    cost = np.ascontiguousarray(s['Q'] + k.T @ s['R'] @ k)
    n = len(x)
    prepared = prepare(f, s['B'], horizon)
    if burn:
        x, _ = nominal_chunk(f, x, rng.normal(size=(burn, n)))
    # Identical counted baseline, chunk sizes, and innovation ordering.
    x, _, values = pulse_chunk(f, s['B'], cost, x, sigma*rng.normal(size=(1,n)), rng.normal(size=(1,horizon,n)))
    previous = values[-1]
    gram, cross, done = np.zeros((n,n)), np.zeros((n,n)), 0
    for budget in budgets:
        while done < budget:
            size = min(256, budget - done)
            pulses = sigma * rng.normal(size=(size,n))
            noises = rng.normal(size=(size,horizon,n))
            x, starts, values = batched_chunk(f, s['B'], cost, x, pulses, noises, prepared)
            delta = np.empty(size)
            delta[0], delta[1:] = values[0]-previous, values[1:]-values[:-1]
            previous = values[-1]
            labels = -pulses * delta[:,None] / (2*sigma**2)
            gram += starts.T @ starts
            cross += labels.T @ starts
            done += size
        z = np.linalg.solve(gram, cross.T).T
        yield budget, x.copy(), z, None, gram/budget, burn+(budget+1)*horizon


def verify():
    checks, benchmarks = [], []
    for n, r in [(6,2),(50,4),(100,4)]:
        task = dict(n=n,m=n,r=r,system_seed=0,family='coupled_unstable',tail=0.,tail_shape='energy',stabilizer='isotropic')
        s = system(task)
        k, h = s['K0'], 16
        f, cost = s['A']-s['B']@k, s['Q']+k.T@s['R']@k
        rng = rng_for(8123,n)
        pulses, noises, x = rng.normal(size=(19,n)), rng.normal(size=(19,h,n)), rng.normal(size=n)
        old = pulse_chunk(f,s['B'],cost,x,pulses,noises)
        new = batched_chunk(f,s['B'],cost,x,pulses,noises,prepare(f,s['B'],h))
        for label,a,b in zip(('endpoint','all_block_starts','all_returns'),old,new):
            assert np.allclose(a,b,rtol=2e-12,atol=2e-11), (n,label)
            checks.append(dict(n=n,test=label,max_absolute_difference=float(np.max(np.abs(a-b)))))
        # This also verifies adjacent baseline, burn-in, RNG consumption,
        # OLS transpose and cumulative prefix counts, not only a block formula.
        outputs = []
        for collector in (pulse_moments,collect):
            begin = time.monotonic()
            values = list(collector(s,k,np.zeros(n),[1024,4096],h,1.,rng_for(9193,n),burn=1024))
            outputs.append((values,time.monotonic()-begin))
        for a,b in zip(outputs[0][0],outputs[1][0]):
            assert a[0]==b[0] and a[-1]==b[-1]
            for idx in (1,2,4):
                assert np.allclose(a[idx],b[idx],rtol=2e-10,atol=2e-10), (n,idx)
        benchmarks.append(dict(n=n,old_seconds=outputs[0][1],batched_seconds=outputs[1][1],
            speedup=outputs[0][1]/outputs[1][1]))
    print(json.dumps(dict(batched_verification='PASS',checks=checks,benchmarks=benchmarks)),flush=True)


if __name__=='__main__':
    from dense_scaling import require_compute
    require_compute(); verify()
