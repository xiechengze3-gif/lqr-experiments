"""Dense, initially unstable LQR scaling study; numerical work requires Slurm."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import socket
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov

if importlib.util.find_spec("numba") is None and os.environ.get("LQR_NUMBA_SITE"):
    sys.path.append(os.environ["LQR_NUMBA_SITE"])
from numba import njit
import numba


def require_compute():
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("All simulations, verification and numerical reporting require Grace Slurm compute nodes")


def rng_for(*parts):
    return np.random.default_rng(np.random.SeedSequence([int(x) for x in parts]))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def op(a):
    return float(np.linalg.norm(a, 2))


def orth(rng, n):
    q, r = np.linalg.qr(rng.normal(size=(n, n)))
    return q * np.where(np.diag(r) >= 0, 1., -1.)


def trunc(a, rank):
    u, s, vt = np.linalg.svd(a, full_matrices=False)
    return (u[:, :rank] * s[:rank]) @ vt[:rank]


def tails(a, rank):
    s = np.linalg.svd(a, compute_uv=False)
    return {"op": float(s[rank]) if rank < len(s) else 0.,
            "fro2": float(s[rank:] @ s[rank:]), "spectrum": s.tolist()}


def psd(a):
    eig, vectors = np.linalg.eigh((a + a.T) / 2)
    return (vectors * np.maximum(eig, 0.)) @ vectors.T


def dare(a, b, q, r):
    p = solve_discrete_are(a, b, q, r)
    return np.linalg.solve(r + b.T @ p @ b, b.T @ p @ a), p


def evaluate(s, k):
    f = s["A"] - s["B"] @ k
    radius = float(np.max(np.abs(np.linalg.eigvals(f))))
    if radius >= 1 - 1e-10 or not np.isfinite(radius):
        return dict(stable=False, rho=radius, gap=None, relative_gap=None, cost=None), None
    p = solve_discrete_lyapunov(f.T, s["Q"] + k.T @ s["R"] @ k)
    value = float(np.trace(p))
    gap = value - s["Jstar"]
    if gap < -1e-7 * max(1., abs(value)):
        raise ArithmeticError("Substantive negative cost gap")
    gap = max(0., gap)
    return dict(stable=True, rho=radius, gap=gap, cost=value,
                relative_gap=gap / s["initial_gap"]), p


def system(task):
    n, rank = task["n"], task["r"]
    if task["m"] != n or not 1 <= rank < n:
        raise ValueError("This study explicitly sets m=n and rank<n")
    rng = rng_for(981113, n, task["system_seed"])
    state_basis, input_basis = orth(rng, n), orth(rng, n)
    q_basis, r_basis = orth(rng, n), orth(rng, n)
    q = (q_basis * np.linspace(1., 3., n)) @ q_basis.T
    r = (r_basis * np.linspace(1., 2.5, n)) @ r_basis.T
    diagonal = rng.uniform(-.60, .65, n)
    diagonal[:rank] = .78
    latent = np.diag(diagonal) + .10 * np.diag(np.ones(n - 1), 1)
    latent += .025 / math.sqrt(n) * rng.normal(size=(n, n))
    latent *= .9 / op(latent)
    f0 = state_basis @ latent @ state_basis.T
    left = state_basis if task["family"] == "coupled_unstable" else orth(rng, n)
    singular = np.zeros(n)
    singular[:rank] = np.linspace(1.2, .9, rank)
    b0 = (left * singular) @ input_basis.T
    initial = np.full(n, .03)
    initial[:rank] = .4 / singular[:rank]
    if task.get("stabilizer")=="isotropic":
        initial[:]=.35
    k0 = (input_basis * initial) @ state_basis.T
    # A and K0 stay IDENTICAL as approximate tails vary on a given (n,r,seed).
    a = f0 + b0 @ k0
    level, shape = task["tail"], task["tail_shape"]
    if shape == "flat":
        singular[rank:] = level
    elif shape == "energy":
        singular[rank:] = level / math.sqrt(n - rank)
    elif shape == "decay":
        singular[rank:] = level * np.arange(1, n - rank + 1, dtype=float) ** -1.5
    else:
        raise ValueError(shape)
    b = (left * singular) @ input_basis.T
    # Uniform dimension/rank-independent bound for all configured tails.
    f_bound = .9 + .03 * .3
    k_bound = .4 / .9
    if task.get("stabilizer")=="isotropic":
        # All configured approximate cells have n-r>=21 and flat tail<=.03.
        # No distinguished singular subspace is visible in the given K0.
        f_bound=.925
        k_bound=.35
    p0 = (3 + 2.5 * k_bound ** 2) / (1 - f_bound ** 2)
    kstar, pstar = dare(a, b, q, r)
    s = dict(A=a, B=b, Q=q, R=r, W=np.eye(n), K0=k0, Kstar=kstar,
             Jstar=float(np.trace(pstar)), p0=p0, input_basis=input_basis[:, :rank])
    f = a - b @ k0
    p_initial = solve_discrete_lyapunov(f.T, q + k0.T @ r @ k0)
    s["initial_gap"] = float(np.trace(p_initial) - s["Jstar"])
    if s["initial_gap"] <= 0 or op(f) > f_bound + 1e-10:
        raise ArithmeticError("Initial certificate failed")
    if task["family"] == "coupled_unstable" and np.max(np.abs(np.linalg.eigvals(a))) <= 1:
        raise ArithmeticError("Main family must be open-loop unstable")
    s["diagnostics"] = dict(Jstar=s["Jstar"], initial_gap=s["initial_gap"], p0_bound=p0,
        p0_actual=op(p_initial), F0_op=op(f), A_op=op(a), B_op=op(b), K0_op=op(k0),
        A_rho=float(np.max(np.abs(np.linalg.eigvals(a)))), Q_condition=3., R_condition=2.5,
        stabilizer=task.get("stabilizer","aligned_spectral_gap"),K0_spectrum=np.linalg.svd(k0,compute_uv=False).tolist(),
        A_nonnormality=op(a.T @ a - a @ a.T), Q_R_commutator=op(q @ r - r @ q),
        B=tails(b, rank), Kstar=tails(kstar, rank),
        density={name:float(np.mean(np.abs(s[name]) > 1e-10)) for name in ("A","B","Q","R","K0")})
    return s


def eta(s):
    return 1 / (2 * (2.5 + 1.2 ** 2 * 2 * s["p0"]))


def targets(s, k, horizon, p=None):
    f = s["A"] - s["B"] @ k
    if p is None:
        p = solve_discrete_lyapunov(f.T, s["Q"] + k.T @ s["R"] @ k)
    fh = np.linalg.matrix_power(f, horizon)
    ph = p - fh.T @ p @ fh
    z, g = -s["B"].T @ p @ f, s["B"].T @ p @ s["B"]
    zh, gh = -s["B"].T @ ph @ f, s["B"].T @ ph @ s["B"]
    return dict(Z=z, G=g, C=g @ k-z, ZH=zh, GH=gh, CH=gh @ k-zh)


def pi_gain(s, g, c, rank=None):
    if rank is None:
        gg, cc = psd(g), c
    else:
        u = np.linalg.svd(np.concatenate((g, c), axis=1), full_matrices=False)[0][:, :rank]
        gg = u @ psd(u.T @ g @ u) @ u.T
        cc = u @ (u.T @ c)
    return np.linalg.solve(s["R"] + gg, cc), gg, cc


@njit(cache=True)
def pulse_chunk(f, b, stage_cost, x, pulses, noises):
    count, horizon, n = noises.shape
    starts = np.empty((count, n))
    returns = np.empty(count)
    for j in range(count):
        starts[j] = x
        total = 0.
        for t in range(horizon):
            x = f @ x + noises[j, t]
            if t == 0:
                x = x + b @ pulses[j]
            total += np.dot(x, stage_cost @ x)
        returns[j] = total
    return x, starts, returns


@njit(cache=True)
def nominal_chunk(f, x, noises):
    states = np.empty_like(noises)
    for j in range(len(noises)):
        x = f @ x + noises[j]
        states[j] = x
    return x, states


@njit(cache=True)
def ce_chunk(f, b, k, x, pulses, noises):
    count, n = noises.shape
    covariates = np.empty((count, 2*n))
    outputs = np.empty((count, n))
    for j in range(count):
        covariates[j, :n] = x
        covariates[j, n:] = -k @ x + pulses[j]
        x = f @ x + b @ pulses[j] + noises[j]
        outputs[j] = x
    return x, covariates, outputs


def nominal_covariance(s, k, x, count, burn, rng):
    f = np.ascontiguousarray(s["A"] - s["B"] @ k)
    if burn:
        x, _ = nominal_chunk(f, x, rng.normal(size=(burn, len(x))))
    gram = np.zeros((len(x), len(x)))
    done = 0
    while done < count:
        size = min(512, count-done)
        x, states = nominal_chunk(f, x, rng.normal(size=(size, len(x))))
        gram += states.T @ states
        done += size
    return x, gram / count


def pulse_moments(s, k, x, budgets, horizon, sigma, rng, burn=512):
    """Yield common prefix statistics, preserving X and adjacent return baseline."""
    f = np.ascontiguousarray(s["A"] - s["B"] @ k)
    cost = np.ascontiguousarray(s["Q"] + k.T @ s["R"] @ k)
    n = len(x)
    if burn:
        x, _ = nominal_chunk(f, x, rng.normal(size=(burn, n)))
    x, _, value = pulse_chunk(f, s["B"], cost, x, sigma*rng.normal(size=(1,n)), rng.normal(size=(1,horizon,n)))
    previous = value[-1]
    gram, cross, g_sum = np.zeros((n,n)), np.zeros((n,n)), np.zeros((n,n))
    done = 0
    for budget in budgets:
        while done < budget:
            size = min(256, budget-done)
            pulses = sigma * rng.normal(size=(size,n))
            noises = rng.normal(size=(size,horizon,n))
            x, starts, values = pulse_chunk(f, s["B"], cost, x, pulses, noises)
            delta = np.empty(size)
            delta[0] = values[0] - previous
            delta[1:] = values[1:] - values[:-1]
            previous = values[-1]
            labels = -pulses * delta[:, None] / (2*sigma**2)
            gram += starts.T @ starts
            cross += labels.T @ starts
            g_sum += ((pulses*delta[:,None]).T @ pulses - sigma**2 * delta.sum()*np.eye(n)) / (2*sigma**4)
            done += size
        zhat = np.linalg.solve(gram, cross.T).T
        ghat = g_sum / budget
        yield budget, x.copy(), zhat, ghat, gram/budget, burn+(budget+1)*horizon


def metric(error):
    return dict(error_op=op(error), error_fro2=float(np.sum(error**2)))


def critic(task, s):
    n, rank, h = task["n"], task["r"], task["horizon"]
    k, x = s["K0"], np.zeros(n)
    # Common nominal prefix: separately estimates the genuine nominal Sigma_K.
    cov_count, cov_burn = 32*n, 512
    x, sigmahat = nominal_covariance(s, k, x, cov_count, cov_burn,
                                     rng_for(116711,n,task["system_seed"],task["trial_seed"]))
    sigmatrue = solve_discrete_lyapunov(s["A"]-s["B"]@k, s["W"])
    true = targets(s,k,h)
    covariance_error = metric(sigmahat-sigmatrue)
    ztr = trunc(true["Z"],rank)
    reference = {
        "NPG":k-eta(s)*(s["R"]@k+true["Z"]),
        "PG":k-eta(s)*(s["R"]@k+true["Z"])@sigmatrue/op(sigmatrue),
        "PI":np.linalg.solve(s["R"]+true["G"],true["C"])}
    records = []
    rng = rng_for(421337,n,task["system_seed"],task["trial_seed"])
    for count,x,raw_z,raw_g,gram,transitions in pulse_moments(s,k,x,task["budgets"],h,task["sigma"],rng):
        total = transitions+cov_count+cov_burn
        raw_c = raw_g@k-raw_z
        for method in ("raw","truncated"):
            z = raw_z if method=="raw" else trunc(raw_z,rank)
            rows = dict(N=count, transitions=total, method=method,
                        gram_min=float(np.linalg.eigvalsh(gram)[0]))
            records.append(dict(rows,mode="critic",algorithm="Z",**metric(z-true["Z"]),
                                finite_error_fro2=float(np.sum((z-true["ZH"])**2))))
            pi,g,c = pi_gain(s,raw_g,raw_c,None if method=="raw" else rank)
            records.append(dict(rows,mode="critic",algorithm="joint",**metric(np.concatenate((g-true["G"],c-true["C"]),axis=1)),
                                finite_error_fro2=float(np.sum((g-true["GH"])**2)+np.sum((c-true["CH"])**2))))
            candidates = {
                "NPG":k-eta(s)*(s["R"]@k+z),
                "PG":k-eta(s)*(s["R"]@k+z)@sigmahat/op(sigmahat),
                "PI":pi}
            for algorithm,candidate in candidates.items():
                quality,_=evaluate(s,candidate)
                records.append(dict(rows,mode="one_step",algorithm=algorithm,**quality,
                                    update_error_fro2=float(np.sum((candidate-reference[algorithm])**2))))
    return records,dict(Z=tails(true["Z"],rank),joint=tails(np.concatenate((true["G"],true["C"]),axis=1),rank),
                        Z_horizon_bias=metric(true["ZH"]-true["Z"]),G_horizon_bias=metric(true["GH"]-true["G"]),
                        Sigma_estimation_error=covariance_error, nominal_covariance_samples=cov_count+cov_burn,
                        eta=eta(s),finite_target_truncation_bias=metric(trunc(true["ZH"],rank)-true["Z"]))


def ce(task,s):
    n, k = task["n"],s["K0"]
    x=np.zeros(n)
    rng=rng_for(633771,n,task["system_seed"],task["trial_seed"])
    f=np.ascontiguousarray(s["A"]-s["B"]@k)
    x,_=nominal_chunk(f,x,rng.normal(size=(512,n)))
    gram,cross=np.zeros((2*n,2*n)),np.zeros((n,2*n))
    records=[]
    done=0
    for budget in task["budgets"]:
        while done<budget:
            size=min(1024,budget-done)
            x,z,y=ce_chunk(f,s["B"],k,x,task["sigma"]*rng.normal(size=(size,n)),rng.normal(size=(size,n)))
            gram+=z.T@z
            cross+=y.T@z
            done+=size
        theta=np.linalg.solve(gram,cross.T).T
        a,b=theta[:,:n],theta[:,n:]
        for method in ("raw","truncated"):
            bhat=b if method=="raw" else trunc(b,task["r"])
            row=dict(mode="ce",algorithm="CE",method=method,N=budget,transitions=budget+512,
                     B_error_fro2=float(np.sum((bhat-s["B"])**2)),A_error_op=op(a-s["A"]))
            try:
                candidate,_=dare(a,bhat,s["Q"],s["R"])
                quality,_=evaluate(s,candidate)
                row.update(quality,policy_error_fro2=float(np.sum((candidate-s["Kstar"])**2)))
            except (ValueError,np.linalg.LinAlgError) as error:
                row.update(stable=False,gap=None,relative_gap=None,failure=str(error))
            records.append(row)
    return records,{}


def deterministic(task,s):
    records=[]
    for algorithm in ("NPG","PG","PI"):
        for method in ("raw","truncated"):
            k=s["K0"].copy()
            stages=task.get("stages",1024) if algorithm=="NPG" else (512 if algorithm=="PG" else 64)
            converged=False
            for stage in range(stages):
                true=targets(s,k,task["horizon"])
                z=true["Z"] if method=="raw" else trunc(true["Z"],task["r"])
                if algorithm=="PI":
                    candidate,_,_=pi_gain(s,true["G"],true["C"],None if method=="raw" else task["r"])
                elif algorithm=="PG":
                    sigma=solve_discrete_lyapunov(s["A"]-s["B"]@k,s["W"])
                    candidate=k-eta(s)*(s["R"]@k+z)@sigma/op(sigma)
                else:
                    candidate=k-eta(s)*(s["R"]@k+z)
                change=op(candidate-k)
                quality,_=evaluate(s,candidate)
                if stage in (0,3,7,15,31,63,127,255,511,1023) or change<1e-7 or not quality["stable"]:
                    records.append(dict(mode="deterministic",algorithm=algorithm,method=method,stage=stage+1,
                                        N=0,transitions=0,last_change_op=change,**quality))
                k=candidate
                if not quality["stable"] or change<1e-7:
                    converged=quality["stable"]
                    break
            records.append(dict(mode="floor_reference",algorithm=algorithm,method=method,stage=stage+1,
                                N=0,transitions=0,converged=converged,last_change_op=change,**quality))
    return records,dict(reference_only=True,eta=eta(s))


def actor(task,s):
    records=[]
    for algorithm in ("NPG","PG","PI"):
        for method in ("raw","truncated"):
            k,x=s["K0"].copy(),np.zeros(task["n"])
            total=0
            stages=task["stages"] if algorithm!="PI" else min(task["stages"],12)
            for stage in range(stages):
                covariance=None
                if algorithm=="PG":
                    x,covariance=nominal_covariance(s,k,x,32*task["n"],512,
                        rng_for(4111,task["n"],task["system_seed"],task["trial_seed"],stage))
                    total+=32*task["n"]+512
                count=task["batch_schedule"][stage]
                rng=rng_for(99111,task["n"],task["system_seed"],task["trial_seed"],stage)
                _,x,raw_z,raw_g,gram,used=next(pulse_moments(s,k,x,[count],task["horizon"],task["sigma"],rng,burn=1024))
                total+=used
                true=targets(s,k,task["horizon"])
                z=raw_z if method=="raw" else trunc(raw_z,task["r"])
                if algorithm=="PI":
                    candidate,_,_=pi_gain(s,raw_g,raw_g@k-raw_z,None if method=="raw" else task["r"])
                elif algorithm=="PG":
                    candidate=k-eta(s)*(s["R"]@k+z)@covariance/op(covariance)
                else:
                    candidate=k-eta(s)*(s["R"]@k+z)
                quality,p=evaluate(s,candidate)
                records.append(dict(mode="actor",algorithm=algorithm,method=method,stage=stage+1,N=count,
                    transitions=total,**quality,residual_error_fro2=float(np.sum((z-true["Z"])**2)),
                    residual_error_op=op(z-true["Z"]),Z_tail_fro2=tails(true["Z"],task["r"])["fro2"],
                    P_op=op(p) if p is not None else None,eta=eta(s)))
                if not quality["stable"]:
                    break
                k=candidate
    return records,dict(schedule=task["batch_schedule"],eta=eta(s),PG="nominal covariance, scalar-normalized step",
                        PI="undamped joint action-block update; raw baseline uses PSD clipping")


def make_manifest(profile):
    if profile in ("isotropic_scaling","isotropic_actor"):
        source="scaling" if profile=="isotropic_scaling" else "actor"
        base=make_manifest(source)
        base["tasks"]=[dict(t,stabilizer="isotropic",budgets=[factor*t["n"] for factor in (128,512,2048,8192)])
                       for t in base["tasks"] if t["trial_seed"]==0] if source=="scaling" else [dict(t,stabilizer="isotropic") for t in base["tasks"] if t["r"]==4]
        base["stabilizer"]="isotropic full-rank K0, all singular values=.35; supplied K0 does not identify a rank-r subspace"
        base["phase"]="Control after discovering input-subspace information in the initial aligned stabilizer"
        return base
    cells=sorted(set([(n,4) for n in (25,50,75,100,150)]+
                     [(50,r) for r in (1,2,4,8,12,16)]+[(100,r) for r in (1,2,4,8,16,24,32)]))
    tasks=[]
    if profile=="scaling":
        for n,rank in cells:
            for system_seed in range(4):
                for trial_seed in range(2):
                    base=dict(n=n,m=n,r=rank,system_seed=system_seed,trial_seed=trial_seed,
                              family="coupled_unstable",tail=0.,tail_shape="energy",horizon=16,sigma=1.)
                    for mode in ("ce","critic"):
                        tasks.append(dict(base,mode=mode,budgets=[factor*n for factor in (8,32,128,512,2048)]))
    elif profile=="approximate":
        for n in (50,100):
            for shape,level in [("energy",x) for x in (0.,.01,.03,.1,.3)]+[("flat",x) for x in (.003,.01,.03)]:
                for system_seed in range(4):
                    base=dict(n=n,m=n,r=4,system_seed=system_seed,trial_seed=0,
                              family="coupled_unstable",tail=level,tail_shape=shape,horizon=16,sigma=1.)
                    tasks.append(dict(base,mode="deterministic",stages=1024))
                    if (shape=="energy" and level in (.03,.1)) or (shape=="flat" and level==.03):
                        for trial_seed in range(2):
                            for mode in ("ce","critic"):
                                tasks.append(dict(base,trial_seed=trial_seed,mode=mode,
                                                  budgets=[factor*n for factor in (8,32,128,512,2048)]))
    elif profile=="actor":
        for n in (50,100):
            for rank,level in [(r,0.) for r in (1,2,4,8)]+[(4,.1)]:
                for system_seed in range(2):
                    tasks.append(dict(n=n,m=n,r=rank,system_seed=system_seed,trial_seed=0,
                        family="coupled_unstable",tail=level,tail_shape="energy",horizon=16,sigma=1.,
                        mode="actor",stages=24,batch_schedule=[16384]*8+[65536]*8+[262144]*8))
    elif profile=="validation":
        for n in (50,100):
            for family in ("coupled_unstable","independent"):
                tasks.append(dict(n=n,m=n,r=4,system_seed=0,trial_seed=0,family=family,tail=.03,
                                  tail_shape="energy",horizon=16,sigma=1.,mode="critic",budgets=[256,1024,4096]))
    else:
        raise ValueError(profile)
    return dict(schema=2,profile=profile,tasks=tasks,absolute_epsilons=[.1,.5,1.,2.,5.],
                target_success=.9,primary_success="fixed declared output budget; first pointwise crossing is descriptive",
                theoretical_targets={"CE":"r*n/epsilon when m=n", "direct_critic":"r*n^2/epsilon when m=n; not an actor result"})


def verify():
    require_compute()
    base=dict(n=12,m=12,r=3,system_seed=0,trial_seed=0,family="coupled_unstable",tail=0.,tail_shape="energy",horizon=16,sigma=1.)
    s=system(base)
    assert s["diagnostics"]["A_rho"]>1 and s["diagnostics"]["F0_op"]<1
    assert np.linalg.matrix_rank(s["K0"])==12 and np.linalg.matrix_rank(s["B"],tol=1e-10)==3
    assert all(density>.99 for density in s["diagnostics"]["density"].values())
    isotropic=system(dict(base,stabilizer="isotropic"))
    np.testing.assert_allclose(isotropic["K0"]@isotropic["K0"].T,.35**2*np.eye(12),atol=1e-12)
    assert isotropic["diagnostics"]["A_rho"]>1 and isotropic["diagnostics"]["F0_op"]<.925
    iso_approx=system(dict(base,stabilizer="isotropic",tail=.1))
    np.testing.assert_allclose(isotropic["A"],iso_approx["A"],atol=1e-12)
    assert evaluate(s,s["Kstar"])[0]["gap"]<1e-8
    approx=system(dict(base,tail=.1))
    np.testing.assert_allclose(approx["A"],s["A"],atol=1e-12)
    np.testing.assert_allclose(approx["K0"],s["K0"],atol=1e-12)
    np.testing.assert_allclose(approx["diagnostics"]["B"]["fro2"],.01,atol=1e-12)
    rng=rng_for(9107)
    f=np.ascontiguousarray(s["A"]-s["B"]@s["K0"])
    cost=s["Q"]+s["K0"].T@s["R"]@s["K0"]
    pulses=rng.normal(size=(9,12)); noises=rng.normal(size=(9,16,12)); x0=rng.normal(size=12)
    x,starts,values=pulse_chunk(f,s["B"],cost,x0.copy(),pulses,noises)
    check=x0.copy(); returns=[]; state_starts=[]
    for j in range(9):
        state_starts.append(check.copy()); value=0.
        for t in range(16):
            check=f@check+noises[j,t]
            if t==0: check+=s["B"]@pulses[j]
            value+=check@cost@check
        returns.append(value)
    np.testing.assert_allclose(x,check,atol=1e-10)
    np.testing.assert_allclose(starts,np.asarray(state_starts),atol=1e-10)
    np.testing.assert_allclose(values,returns,atol=1e-9)
    # Stein second-order identity at a fixed state: isolates curvature label.
    t=targets(s,s["K0"],16)
    pulse=rng.normal(size=(100000,12))
    fixed=rng.normal(size=12)
    quadratic=2*pulse@(-t["ZH"])@fixed+np.einsum("bi,ij,bj->b",pulse,t["GH"],pulse)
    weighted=pulse*(quadratic-quadratic.mean())[:,None]
    gh=weighted.T@pulse/(2*len(pulse))
    assert np.linalg.norm(gh-t["GH"],"fro")/np.linalg.norm(t["GH"],"fro")<.08
    gain,gg,cc=pi_gain(s,t["G"],t["C"],3)
    exact=np.linalg.solve(s["R"]+t["G"],t["C"])
    np.testing.assert_allclose(gain,exact,atol=1e-9)
    assert np.linalg.eigvalsh(s["R"]+gg)[0]>=1-1e-10
    rows,_=deterministic(dict(base,stages=512),s)
    finals=[r for r in rows if r["mode"]=="floor_reference"]
    assert all(r["stable"] and r["gap"]<.05*s["initial_gap"] for r in finals)
    for algorithm in ("NPG","PG","PI"):
        pair=[r for r in finals if r["algorithm"]==algorithm]
        np.testing.assert_allclose(pair[0]["gap"],pair[1]["gap"],atol=1e-7)
    for mode,fn in (("ce",ce),("critic",critic)):
        rows,_=fn(dict(base,budgets=[128,512]),s)
        assert rows and all(row["transitions"]>=row["N"] for row in rows)
    print(json.dumps(dict(verified=True,numba=numba.__version__,tests=["dense unstable family","uniform bounds",
        "full rank stabilizer","fixed A across tails","compiled trajectory matches reference",
        "second-order Stein label","joint PI/general dense R","exact NPG/PG/PI convergence","collectors"])),flush=True)


def run(path,task_id,output):
    require_compute()
    data=Path(path).read_bytes(); manifest=json.loads(data); task=manifest["tasks"][task_id]
    destination=Path(output)/f"task-{task_id:05d}.json"
    if destination.exists():
        raise RuntimeError("Refuse overwrite of previous task output")
    start=time.time()
    payload=dict(task_id=task_id,task=task,manifest_sha256=hashlib.sha256(data).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),host=socket.gethostname(),
        slurm_job_id=os.environ["SLURM_JOB_ID"],python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__)
    try:
        s=system(task)
        records,diagnostics={"ce":ce,"critic":critic,"deterministic":deterministic,"actor":actor}[task["mode"]](task,s)
        payload.update(status="complete",records=records,diagnostics=dict(s["diagnostics"],**diagnostics))
    except Exception as error:
        payload.update(status="failed",failure=f"{type(error).__name__}: {error}",records=[])
        raise
    finally:
        payload["wall_seconds"]=time.time()-start
        atomic_json(destination,payload)
    print(f"COMPLETE {task_id} {task['mode']} n={task['n']} r={task['r']} seconds={payload['wall_seconds']:.2f}",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("plan"); p.add_argument("--profile",choices=["scaling","approximate","actor","validation","isotropic_scaling","isotropic_actor"],required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("run"); p.add_argument("--manifest",required=True); p.add_argument("--task-id",type=int,required=True); p.add_argument("--output",required=True)
    sub.add_parser("verify")
    args=parser.parse_args()
    if args.command=="plan":
        manifest=make_manifest(args.profile); atomic_json(args.output,manifest); print(len(manifest["tasks"]))
    elif args.command=="verify": verify()
    else: run(args.manifest,args.task_id,args.output)
