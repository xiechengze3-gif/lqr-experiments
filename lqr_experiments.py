"""Paired rank ablations. All simulation commands require a Slurm allocation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import socket
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov


def require_compute():
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Simulation and numerical verification must run on Grace compute nodes through Slurm.")


def seed_rng(*parts):
    return np.random.default_rng(np.random.SeedSequence([int(p) for p in parts]))


def orthogonal(rng, size):
    u, t = np.linalg.qr(rng.normal(size=(size, size)))
    return u * np.where(np.diag(t) >= 0, 1, -1)


def truncate(matrix, rank):
    u, s, vt = np.linalg.svd(matrix, full_matrices=False)
    return (u[:, :rank] * s[:rank]) @ vt[:rank]


def spectral(matrix):
    return float(np.linalg.norm(matrix, 2))


def tail_metrics(matrix, rank):
    s = np.linalg.svd(matrix, compute_uv=False)
    return {"tail_op": float(s[rank]) if rank < len(s) else 0.,
            "tail_fro2": float(s[rank:] @ s[rank:]),
            "singular_values": s.tolist()}


def lqr(a, b, q, r):
    p = solve_discrete_are(a, b, q, r)
    return np.linalg.solve(r + b.T @ p @ b, b.T @ p @ a), p


def evaluate(system, k):
    f = system["A"] - system["B"] @ k
    radius = float(np.max(np.abs(np.linalg.eigvals(f))))
    if not np.isfinite(radius) or radius >= 1 - 1e-10:
        return {"stable": False, "rho": radius, "cost": None, "gap": None,
                "relative_gap": None}, None
    s = system["Q"] + k.T @ system["R"] @ k
    p = solve_discrete_lyapunov(f.T, s)
    cost = float(np.trace(system["W"] @ p))
    # Do not clamp a substantive negative gap: it would conceal a numerical bug.
    gap = cost - system["Jstar"]
    if gap < -1e-7 * max(1., abs(cost)):
        raise ArithmeticError(f"Negative optimality gap: {gap}")
    gap = max(0., gap)
    return {"stable": True, "rho": radius, "cost": cost, "gap": gap,
            "relative_gap": gap / system["initial_gap"]}, p


def make_system(task):
    n, m, rank = task["n"], task["m"], task["r"]
    d = min(n, m)
    if not 1 <= rank <= d:
        raise ValueError("Invalid structural rank")
    rng = seed_rng(71291, n, m, task["system_seed"])
    # Reuse rotations across r and tail settings. All scalar bounds stay fixed.
    a = task.get("a_norm", .8) * orthogonal(rng, n)
    u, v = orthogonal(rng, n), orthogonal(rng, m)
    singular = np.ones(d)
    tau = task["tail"]
    shape = task.get("tail_shape", "flat")
    if shape == "flat":
        singular[rank:] = tau
    elif shape == "energy":
        singular[rank:] = tau / math.sqrt(max(1, d - rank))
    elif shape == "decay":
        singular[rank:] = tau * np.arange(1, d - rank + 1, dtype=float) ** -1.5
    else:
        raise ValueError(shape)
    b = (u[:, :d] * singular) @ v[:, :d].T
    q, r, w = np.eye(n), np.eye(m), np.eye(n)
    amplitude = task.get("k0_norm", 0.)
    k0 = amplitude * orthogonal(rng, m)[:, :d] @ orthogonal(rng, n)[:, :d].T
    f_bound = task.get("a_norm", .8) + amplitude
    if f_bound >= 1 or not 0 <= tau <= 1:
        raise ValueError("Scalar certificate or spectrum out of range")
    p0 = (1 + amplitude ** 2) / (1 - f_bound ** 2)
    kstar, pstar = lqr(a, b, q, r)
    system = dict(A=a, B=b, Q=q, R=r, W=w, K0=k0, Kstar=kstar,
                  Jstar=float(np.trace(pstar)), p0=p0, input_basis=v[:, :rank])
    p_initial = solve_discrete_lyapunov((a - b @ k0).T, q + k0.T @ r @ k0)
    system["initial_gap"] = float(np.trace(p_initial) - np.trace(pstar))
    if system["initial_gap"] <= 1e-12:
        raise ValueError("Degenerate initial cost gap")
    system["diagnostics"] = {"B": tail_metrics(b, rank),
                             "Kstar": tail_metrics(kstar, rank),
                             "p0_bound": p0, "Jstar": system["Jstar"],
                             "initial_gap": system["initial_gap"],
                             "a_norm": spectral(a), "b_norm": spectral(b)}
    return system


def actor_step(system):
    # Supplied dimension-independent scalar certificate; never tune on true A/B.
    return 1 / (2 * (1 + 2 * system["p0"]))


def burn_blocks(system, x, horizon, sigma):
    pbar = 2 * system["p0"]
    kappa = math.sqrt(pbar)
    rho = math.sqrt(1 - 1 / pbar)
    lam = (1 + sigma ** 2) * kappa ** 2 / (1 - rho ** 2)
    value = kappa ** 2 * (float(x @ x) + len(x) * lam)
    return max(0, math.ceil(math.log(max(1., value)) / (-2 * horizon * math.log(rho))))


def pulse_block(system, k, x, horizon, sigma, rng, dynamics=None):
    """G uses states s=1..H, including nominal cost of terminal state."""
    f, s = dynamics if dynamics is not None else (
        system["A"] - system["B"] @ k, system["Q"] + k.T @ system["R"] @ k)
    pulse = sigma * rng.normal(size=k.shape[0])
    noises = rng.normal(size=(horizon, len(x)))
    start = x.copy()
    total = 0.
    for index in range(horizon):
        x = f @ x + noises[index]
        if index == 0:
            x = x + system["B"] @ pulse
        total += float(x @ s @ x)
    if not np.isfinite(total) or not np.all(np.isfinite(x)):
        raise ArithmeticError("Non-finite trajectory")
    return x, start, pulse, total


def regression(cross, gram, count):
    eig = np.linalg.eigvalsh(gram / count)
    return cross @ np.linalg.pinv(gram, rcond=1e-12), {
        "gram_min": float(eig[0]), "gram_condition": float(eig[-1] / eig[0]) if eig[0] > 0 else None,
        "gram_rank": int(np.linalg.matrix_rank(gram))}


def residual_targets(system, k, horizon):
    f = system["A"] - system["B"] @ k
    s = system["Q"] + k.T @ system["R"] @ k
    p = solve_discrete_lyapunov(f.T, s)
    ph = np.zeros_like(p)
    for _ in range(horizon):
        ph = s + f.T @ ph @ f
    return -system["B"].T @ p @ f, -system["B"].T @ ph @ f


def error_metrics(estimate, target):
    error = estimate - target
    return {"error_op": spectral(error), "error_fro2": float(np.sum(error ** 2))}


def critic(task, system):
    n, m, rank = task["n"], task["m"], task["r"]
    h, sigma = task["horizon"], task["sigma"]
    rng = seed_rng(80317, n, m, task["system_seed"], task["trial_seed"])
    x, k = np.zeros(n), system["K0"]
    dynamics = (system["A"] - system["B"] @ k, system["Q"] + k.T @ system["R"] @ k)
    burn = burn_blocks(system, x, h, sigma)
    for _ in range(burn):
        x, _, _, _ = pulse_block(system, k, x, h, sigma, rng, dynamics)
    x, _, _, previous = pulse_block(system, k, x, h, sigma, rng, dynamics)
    z, zh = residual_targets(system, k, h)
    gram, cross = np.zeros((n, n)), np.zeros((m, n))
    ranks = sorted(set([max(1, rank // 2), rank, min(2 * rank, min(n, m))]))
    records = []
    for count in range(1, max(task["budgets"]) + 1):
        x, start, pulse, value = pulse_block(system, k, x, h, sigma, rng, dynamics)
        label = -pulse * (value - previous) / (2 * sigma ** 2)
        previous = value
        gram += np.outer(start, start)
        cross += np.outer(label, start)
        if count not in task["budgets"]:
            continue
        raw, gram_info = regression(cross, gram, count)
        variants = {"raw": raw}
        variants.update({f"rank_{r}": truncate(raw, r) for r in ranks})
        basis = system["input_basis"]
        variants["oracle_subspace"] = basis @ (basis.T @ raw)
        for method, estimate in variants.items():
            k_next = k - actor_step(system) * (system["R"] @ k + estimate)
            quality, _ = evaluate(system, k_next)
            record = dict(mode="critic", method=method, N=count,
                          transitions=(burn + count + 1) * h, **gram_info,
                          **error_metrics(estimate, z), **quality)
            record["error_to_finite_target_fro2"] = float(np.sum((estimate - zh) ** 2))
            records.append(record)
    return records, {"Z": tail_metrics(z, rank), "Z_H": tail_metrics(zh, rank),
                     "horizon_bias": error_metrics(zh, z), "burn_blocks": burn}


def ce(task, system):
    n, m, rank = task["n"], task["m"], task["r"]
    sigma = task["sigma"]
    rng = seed_rng(92713, n, m, task["system_seed"], task["trial_seed"])
    k0, x = system["K0"], np.zeros(n)
    # Burn-in is charged even though OLS does not require a stationary start.
    burn = burn_blocks(system, x, 1, sigma)
    gram, cross = np.zeros((n + m, n + m)), np.zeros((n, n + m))
    records = []
    ranks = sorted(set([max(1, rank // 2), rank, min(2 * rank, min(n, m))]))
    for step in range(burn + max(task["budgets"])):
        action = -k0 @ x + sigma * rng.normal(size=m)
        nxt = system["A"] @ x + system["B"] @ action + rng.normal(size=n)
        if step >= burn:
            covariate = np.concatenate((x, action))
            gram += np.outer(covariate, covariate)
            cross += np.outer(nxt, covariate)
        x = nxt
        count = step - burn + 1
        if count not in task["budgets"]:
            continue
        theta, gram_info = regression(cross, gram, count)
        ahat, bhat = theta[:, :n], theta[:, n:]
        variants = {"raw": bhat}
        variants.update({f"B_rank_{r}": truncate(bhat, r) for r in ranks})
        basis = system["input_basis"]
        variants["oracle_subspace"] = bhat @ basis @ basis.T
        raw_gain = None
        for method, b_est in variants.items():
            record = dict(mode="ce", method=method, N=count, transitions=burn + count,
                          **gram_info, A_error_op=spectral(ahat - system["A"]),
                          B_error_op=spectral(b_est - system["B"]),
                          B_error_fro2=float(np.sum((b_est - system["B"]) ** 2)))
            try:
                gain, _ = lqr(ahat, b_est, system["Q"], system["R"])
                quality, _ = evaluate(system, gain)
                record.update(quality)
                record["gain_error_fro2"] = float(np.sum((gain - system["Kstar"]) ** 2))
                if method == "raw":
                    raw_gain = gain
            except (np.linalg.LinAlgError, ValueError) as exc:
                record.update(stable=False, cost=None, gap=None, relative_gap=None,
                              failure=f"{type(exc).__name__}: {exc}")
            records.append(record)
        for r in ranks:
            record = dict(mode="ce", method=f"K_rank_{r}", N=count,
                          transitions=burn + count, **gram_info)
            if raw_gain is None:
                record.update(stable=False, cost=None, gap=None, relative_gap=None,
                              failure="Raw Riccati solve failed")
            else:
                gain = truncate(raw_gain, r)
                quality, _ = evaluate(system, gain)
                record.update(quality, gain_error_fro2=float(np.sum((gain - system["Kstar"]) ** 2)))
            records.append(record)
    return records, {}


def actor(task, system):
    n, m, rank = task["n"], task["m"], task["r"]
    h, sigma, count = task["horizon"], task["sigma"], task["batch_blocks"]
    eta = actor_step(system)
    records = []
    for method in ("raw", f"rank_{rank}", "oracle_subspace"):
        # Each method has its own continuous trajectory. Equal random seeds pair
        # innovations; different policies naturally generate different states.
        rng = seed_rng(11927, n, m, task["system_seed"], task["trial_seed"])
        x, k = np.zeros(n), system["K0"].copy()
        transitions = 0
        quality, _ = evaluate(system, k)
        records.append(dict(mode="actor", method=method, stage=0, N=0,
                            transitions=0, **quality))
        # Fix the burn count in advance, for identical primitive budgets across
        # methods, using the scalar certificate and a conservative state radius.
        radius = np.full(n, 100. * math.sqrt(2 * system["p0"]))
        burn = burn_blocks(system, radius, h, sigma)
        for stage in range(task["stages"]):
            dynamics = (system["A"] - system["B"] @ k, system["Q"] + k.T @ system["R"] @ k)
            for _ in range(burn):
                x, _, _, _ = pulse_block(system, k, x, h, sigma, rng, dynamics)
            x, _, _, previous = pulse_block(system, k, x, h, sigma, rng, dynamics)
            gram, cross = np.zeros((n, n)), np.zeros((m, n))
            for _ in range(count):
                x, start, pulse, value = pulse_block(system, k, x, h, sigma, rng, dynamics)
                label = -pulse * (value - previous) / (2 * sigma ** 2)
                previous = value
                gram += np.outer(start, start)
                cross += np.outer(label, start)
            raw, gram_info = regression(cross, gram, count)
            if method == "raw":
                estimate = raw
            elif method == "oracle_subspace":
                basis = system["input_basis"]
                estimate = basis @ (basis.T @ raw)
            else:
                estimate = truncate(raw, rank)
            z, zh = residual_targets(system, k, h)
            candidate = k - eta * (system["R"] @ k + estimate)
            transitions += (burn + count + 1) * h
            quality, p = evaluate(system, candidate)
            record = dict(mode="actor", method=method, stage=stage + 1,
                          N=(stage + 1) * count, transitions=transitions,
                          **quality, **gram_info, **error_metrics(estimate, z),
                          Z_tail_op=tail_metrics(z, rank)["tail_op"],
                          Z_tail_fro2=tail_metrics(z, rank)["tail_fro2"],
                          horizon_bias_op=spectral(zh - z), burn_blocks=burn)
            # Evaluation is diagnostics only: never reject, backtrack, or tune a
            # stable update using true dynamics. Instability terminates the run.
            record["containment_ratio"] = float(spectral(p) / system["p0"]) if p is not None else None
            records.append(record)
            if not quality["stable"]:
                break
            k = candidate
    return records, {"eta": eta, "schedule": "fixed batch, fixed certificate-based burn"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def make_tasks(profile):
    # Pilot diagnoses noise and tail floors before expensive scaling sweeps.
    if profile == "pilot":
        cases = [(n, 2, tau, "flat") for n in (16, 32) for tau in (0., .05, .2)]
        systems, trials = 2, 2
        budgets = [256, 1024, 4096, 16384]
        batches, stages = [512, 2048], 32
    elif profile == "scaling":
        cases = sorted(set([(n, 2, 0., "flat") for n in (16, 32, 64, 128)] +
                           [(64, r, 0., "flat") for r in (1, 2, 4, 8, 16)] +
                           [(n, 2, tau, shape) for n in (32, 64) for tau in (.01, .03, .1, .3)
                            for shape in ("flat", "energy", "decay")]))
        systems, trials = 8, 8
        budgets = [512, 2048, 8192, 32768, 131072]
        batches, stages = [2048, 8192, 32768], 64
    else:
        raise ValueError(profile)
    tasks = []
    for n, rank, tau, shape in cases:
        for system_seed in range(systems):
            for trial_seed in range(trials):
                base = dict(n=n, m=n, r=rank, tail=tau, tail_shape=shape,
                            system_seed=system_seed, trial_seed=trial_seed,
                            horizon=12, sigma=1., a_norm=.8, k0_norm=0.)
                for mode in ("critic", "ce"):
                    tasks.append(dict(base, mode=mode, budgets=budgets))
                for batch in batches:
                    tasks.append(dict(base, mode="actor", batch_blocks=batch, stages=stages))
    return {"schema": 1, "profile": profile, "tasks": tasks,
            "absolute_epsilons": [.05, .1, .2, .5, 1.],
            "relative_epsilons": [.01, .05, .1], "target_success": .9}


def run_task(manifest_path, task_id, output):
    require_compute()
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    task = manifest["tasks"][task_id]
    destination = Path(output) / f"task-{task_id:05d}.json"
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if destination.exists():
        previous = json.loads(destination.read_text())
        if previous["manifest_sha256"] != manifest_hash or previous["task"] != task:
            raise RuntimeError("Existing task output belongs to another manifest")
        if previous.get("status") == "complete":
            print(f"SKIP complete task {task_id}", flush=True)
            return
        raise RuntimeError("Failed task output exists; retry into a new output directory")
    started = time.time()
    payload = dict(task_id=task_id, task=task, manifest_sha256=manifest_hash,
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   host=socket.gethostname(), slurm_job_id=os.environ["SLURM_JOB_ID"],
                   slurm_array_task_id=os.environ.get("SLURM_ARRAY_TASK_ID"),
                   python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)
    try:
        system = make_system(task)
        records, diagnostics = {"critic": critic, "ce": ce, "actor": actor}[task["mode"]](task, system)
        payload.update(status="complete", records=records,
                       diagnostics=dict(system["diagnostics"], **diagnostics))
    except Exception as exc:
        payload.update(status="failed", failure=f"{type(exc).__name__}: {exc}", records=[])
        raise
    finally:
        payload["wall_seconds"] = time.time() - started
        atomic_json(destination, payload)
    print(f"COMPLETE task={task_id} mode={task['mode']} seconds={payload['wall_seconds']:.2f}", flush=True)


def verify():
    require_compute()
    base = dict(n=8, m=8, r=2, tail=0., tail_shape="flat", system_seed=0,
                trial_seed=0, horizon=12, sigma=1., a_norm=.8, k0_norm=.03)
    system = make_system(base)
    assert np.linalg.matrix_rank(system["B"]) == 2
    initial, _ = evaluate(system, system["K0"])
    optimum, _ = evaluate(system, system["Kstar"])
    assert initial["stable"] and optimum["gap"] < 1e-9
    z, zh = residual_targets(system, system["K0"], base["horizon"])
    f = system["A"] - system["B"] @ system["K0"]
    p = solve_discrete_lyapunov(f.T, system["Q"] + system["K0"].T @ system["K0"])
    fh = np.linalg.matrix_power(f, base["horizon"])
    np.testing.assert_allclose(zh - z, system["B"].T @ fh.T @ p @ fh @ f, atol=1e-12)
    assert np.linalg.matrix_rank(z, tol=1e-10) == 2
    assert np.linalg.matrix_rank(system["K0"]) == 8
    # Noise-free infinite-sample fixed-policy updates isolate algorithmic bias.
    k = system["K0"].copy()
    for _ in range(200):
        true_z, _ = residual_targets(system, k, base["horizon"])
        k = k - actor_step(system) * (k + truncate(true_z, 2))
    quality, _ = evaluate(system, k)
    assert quality["stable"] and quality["gap"] < 1e-7
    approximate = make_system(dict(base, tail=.1))
    assert np.linalg.matrix_rank(approximate["B"]) == 8
    np.testing.assert_allclose(approximate["diagnostics"]["B"]["tail_fro2"], .06, atol=1e-12)
    # Check expected label sign and terminal indexing via Gaussian Monte Carlo
    # at a fixed state. This is a test fixture, never an experimental sampler.
    rng = seed_rng(11391)
    x = rng.normal(size=8)
    count = 50000
    pulses = rng.normal(size=(count, 8))
    conditional = (x @ f.T @ (solve_discrete_lyapunov(f.T, system["Q"] + system["K0"].T @ system["K0"]) - fh.T @ p @ fh) @ f @ x
                   + 2 * pulses @ (-zh) @ x
                   + np.einsum("bi,ij,bj->b", pulses, system["B"].T @ (p - fh.T @ p @ fh) @ system["B"], pulses))
    centered = conditional - np.mean(conditional)
    labels = -pulses * centered[:, None] / 2
    means = labels.mean(axis=0)
    standard = labels.std(axis=0, ddof=1) / math.sqrt(count)
    assert np.all(np.abs(means - zh @ x) < 7 * standard + .01)
    # Validate real collectors, primitive budgets, paired truncation, and CE.
    for mode, function in (("critic", critic), ("ce", ce), ("actor", actor)):
        tiny = dict(base, mode=mode, budgets=[128, 256], batch_blocks=128, stages=2)
        records, _ = function(tiny, system)
        assert records and all(row["transitions"] >= row.get("N", 0) for row in records)
        if mode == "actor":
            costs = {row["transitions"] for row in records if row["stage"] == 1}
            assert len(costs) == 1
    print(json.dumps({"verified": True, "tests": ["rank", "cost identity", "horizon identity",
                      "full-rank K0", "exact NPG convergence", "approximate tails",
                      "Gaussian label mean", "collectors", "paired primitive budgets"]}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--profile", choices=["pilot", "scaling"], default="pilot")
    plan.add_argument("--output", required=True)
    run = sub.add_parser("run")
    run.add_argument("--manifest", required=True)
    run.add_argument("--task-id", type=int, required=True)
    run.add_argument("--output", required=True)
    sub.add_parser("verify")
    args = parser.parse_args()
    if args.command == "plan":
        tasks = make_tasks(args.profile)
        atomic_json(args.output, tasks)
        print(f"Created {len(tasks['tasks'])} tasks")
    elif args.command == "verify":
        verify()
    else:
        run_task(args.manifest, args.task_id, args.output)


if __name__ == "__main__":
    main()
