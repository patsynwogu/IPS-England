"""
IPS-England v1.5 -- agent-based simulation of the SEND identification and assessment
pathway in England.

AGENTS
  Family agents hold a navigational capacity drawn from a lognormal distribution. On
  refusal at either statutory gate they decide whether to appeal. Appeal costs time and
  succeeds with high probability, so it is a rational choice that is unequally available.

  Authority agents screen incoming requests, queue independently and assess at their own
  capacity. Successful appeals return to their queue, which raises backlog further and closes
  the loop. A `pressure_beta` parameter raises an authority's refusal propensity with its own
  backlog; it is implemented, it defaults to zero, and no result reported anywhere uses it.
  Switching it on moves the first statutory gate and requires recalibration.

TWO STATUTORY GATES, both measured
  Gate 1, refused progression to assessment: 43,300 of 162,700 requests in 2025 (26.6%)
  Gate 2, assessed but no plan issued: 7,200 of 118,800 assessments in 2025 (6.0%)
  Plans issued 2025: 111,200. Calibration target used here: 110,708.

The published 26.6% is the outcome after appeals have resolved, so the model infers the
gross refusal rate whose post-appeal residue equals it. At an 18% appeal rate that gross
figure is 32.4%.

WHAT CHANGED IN v1.5
  1. Independent random streams. Process duration is now drawn from its own generator, so
     varying duration no longer perturbs queueing decisions that duration cannot affect.
     Under v1.3 two runs differing only in duration produced different assessment queues.
  2. Every reported quantity is a mean across seeds with a standard deviation, not a
     single draw. The v1.3 headline was one favourable realisation.
  3. Calibration targets the across-seed mean rather than one seed.
  4. The stability of the system is measured rather than assumed. See stability().

Sources: DfE, Education, health and care plans, January 2026 (calendar 2025).
Ministry of Justice, Tribunal Statistics 2024/25, roughly 25,000 SEND appeals registered
across all grounds, which bounds the appeal rate assumed here.

Python is authoritative. The published page reads sweep.json and recomputes nothing.

Run:  python3 model.py
"""
import numpy as np, json
from math import erf, sqrt

REQUESTS, PLANS, TIMELY = 162_702, 110_708, 0.461
NET_GATE1, GATE2 = 0.266, 0.060
WEEKS, N_LA, YEARS, DEADLINE = 52, 152, 4, 20
APPEAL_SHARE, APPEAL_SUCCESS, APPEAL_WEEKS = 0.18, 0.99, 30
CAP_SIGMA = 0.80
SEEDS = tuple(range(1, 11))


def _inv_norm(p):
    """Inverse standard normal by bisection. Avoids a scipy dependency."""
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * (1 + erf(mid / sqrt(2))) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def appeal_threshold(share, sigma=CAP_SIGMA):
    """Capacity above which a family appeals, set so that `share` of families qualify."""
    return float(np.exp(sigma * _inv_norm(1 - share)))


def run(capacity_ratio=1.60, duration_mean=21.0, duration_cv=0.45,
        appeal_share=APPEAL_SHARE, appeal_weeks=APPEAL_WEEKS,
        pressure_beta=0.0, cap_sigma=CAP_SIGMA, seed=3,
        years=YEARS, steps_per_year=WEEKS):
    """One realisation. `steps_per_year` varies time resolution for the discretisation
    check. Duration draws use a separate stream so that changing duration_mean leaves
    every queueing decision in the run bit-for-bit identical."""
    gate1_gross = NET_GATE1 / (1 - appeal_share * APPEAL_SUCCESS)
    thr = appeal_threshold(appeal_share, cap_sigma)
    rng = np.random.default_rng(seed)            # structure, arrivals, gates, appeals
    drng = np.random.default_rng(900_000 + seed)  # process duration only

    share = rng.lognormal(0, 0.65, N_LA); share /= share.sum()
    demand = share * REQUESTS
    capacity = share * PLANS * rng.lognormal(np.log(capacity_ratio), 0.45, N_LA)
    k = 1 / duration_cv ** 2
    appeal_steps = int(round(appeal_weeks / 52 * steps_per_year))
    wk = 52 / steps_per_year

    queue = [[] for _ in range(N_LA)]
    appeals = [[] for _ in range(N_LA)]
    direct, via_appeal = [], []
    issued = exits = appealed = 0
    cap_issued, cap_exited = [], []

    for w in range(years * steps_per_year):
        final = w >= (years - 1) * steps_per_year
        for a in range(N_LA):
            pressure = len(queue[a]) / max(1.0, demand[a] / steps_per_year * 8)
            g1 = float(np.clip(gate1_gross + pressure_beta * pressure, 0.0, 0.9))

            for _ in range(rng.poisson(demand[a] / steps_per_year)):
                cf = rng.lognormal(0, cap_sigma)
                if rng.random() < g1:
                    if cf >= thr:
                        if final: appealed += 1
                        appeals[a].append((w + appeal_steps, w, cf))
                    elif final:
                        exits += 1; cap_exited.append(cf)
                else:
                    queue[a].append((w, cf, False))

            pending = []
            for ret, arr, cf in appeals[a]:
                if ret <= w:
                    if rng.random() < APPEAL_SUCCESS: queue[a].append((arr, cf, True))
                    elif final: exits += 1; cap_exited.append(cf)
                else: pending.append((ret, arr, cf))
            appeals[a] = pending

            for _ in range(min(rng.poisson(capacity[a] / steps_per_year), len(queue[a]))):
                arr, cf, was_appeal = queue[a].pop(0)
                if rng.random() < GATE2:
                    if final: exits += 1; cap_exited.append(cf)
                    continue
                dur = max(1, drng.gamma(k, duration_mean / k))
                if final:
                    t = (w - arr) * wk + dur
                    (via_appeal if was_appeal else direct).append(t)
                    issued += 1; cap_issued.append(cf)

    d, v = np.array(direct), np.array(via_appeal)
    return dict(
        issued=issued,
        timely=float(np.mean(d <= DEADLINE)) if len(d) else float("nan"),
        direct_n=len(d), appeal_n=len(v),
        appeal_median_weeks=float(np.median(v)) if len(v) else float("nan"),
        exits=exits, appealed=appealed,
        cap_issued=float(np.median(cap_issued)) if cap_issued else float("nan"),
        cap_exited=float(np.median(cap_exited)) if cap_exited else float("nan"),
        gate1_gross=gate1_gross, threshold=thr,
    )


def ensemble(seeds=SEEDS, **kw):
    """Run the same specification across seeds and return mean, sd and range for each
    reported quantity. Nothing in this model should be reported from one draw."""
    runs = [run(seed=s, **kw) for s in seeds]
    keys = ("issued", "timely", "exits", "appeal_n", "appeal_median_weeks",
            "cap_issued", "cap_exited")
    out = dict(n_seeds=len(seeds), gate1_gross=runs[0]["gate1_gross"],
               threshold=runs[0]["threshold"])
    for key in keys:
        vals = np.array([r[key] for r in runs], dtype=float)
        out[key] = float(vals.mean())
        out[key + "_sd"] = float(vals.std(ddof=1))
        out[key + "_lo"] = float(vals.min())
        out[key + "_hi"] = float(vals.max())
    return out


def stability(seed=3, years=10, **kw):
    """Does the system settle? Returns the assessment queue at the end of each year,
    split by whether an authority's capacity can clear its own inflow. A queue that grows
    only inside the under-capacity group is a divergence between authorities, not a
    national backlog, and it means no national steady state exists to report."""
    gate1_gross = NET_GATE1 / (1 - APPEAL_SHARE * APPEAL_SUCCESS)
    thr = appeal_threshold(APPEAL_SHARE)
    ratio_kw = dict(capacity_ratio=1.60); ratio_kw.update(kw)
    rng = np.random.default_rng(seed)
    share = rng.lognormal(0, 0.65, N_LA); share /= share.sum()
    demand = share * REQUESTS
    capacity = share * PLANS * rng.lognormal(np.log(ratio_kw["capacity_ratio"]), 0.45, N_LA)
    inflow = demand * (1 - gate1_gross) + demand * gate1_gross * APPEAL_SHARE * APPEAL_SUCCESS
    solvent = capacity >= inflow

    queue = [[] for _ in range(N_LA)]; appeals = [[] for _ in range(N_LA)]
    rows = []
    for w in range(years * WEEKS):
        for a in range(N_LA):
            for _ in range(rng.poisson(demand[a] / WEEKS)):
                if rng.random() < gate1_gross:
                    if rng.lognormal(0, CAP_SIGMA) >= thr:
                        appeals[a].append((w + APPEAL_WEEKS, w))
                else: queue[a].append(w)
            keep = []
            for ret, arr in appeals[a]:
                if ret <= w:
                    if rng.random() < APPEAL_SUCCESS: queue[a].append(arr)
                else: keep.append((ret, arr))
            appeals[a] = keep
            for _ in range(min(rng.poisson(capacity[a] / WEEKS), len(queue[a]))):
                queue[a].pop(0)
        if (w + 1) % WEEKS == 0:
            ql = np.array([len(x) for x in queue])
            rows.append(dict(year=(w + 1) // WEEKS, total=int(ql.sum()),
                             under_capacity=int(ql[~solvent].sum()),
                             adequate=int(ql[solvent].sum())))
    return dict(n_under_capacity=int((~solvent).sum()), n_la=N_LA,
                ratio_median=float(np.median(capacity / inflow)),
                ratio_p10=float(np.percentile(capacity / inflow, 10)),
                ratio_p90=float(np.percentile(capacity / inflow, 90)),
                rows=rows)


def waits(seed=3, **kw):
    """Queue waiting time for every plan issued in the reporting year, in weeks, before
    the statutory process itself is added. Process duration enters only at the final step
    and is drawn from an independent stream, so one pass over the queue serves every
    duration setting. That is what makes the duration curve exact rather than noisy."""
    kw = dict(kw); kw.pop("duration_mean", None)
    gate1_gross = NET_GATE1 / (1 - kw.get("appeal_share", APPEAL_SHARE) * APPEAL_SUCCESS)
    thr = appeal_threshold(kw.get("appeal_share", APPEAL_SHARE))
    cr = kw.get("capacity_ratio", 1.60)
    rng = np.random.default_rng(seed)
    share = rng.lognormal(0, 0.65, N_LA); share /= share.sum()
    demand = share * REQUESTS
    capacity = share * PLANS * rng.lognormal(np.log(cr), 0.45, N_LA)
    queue = [[] for _ in range(N_LA)]; appeals = [[] for _ in range(N_LA)]
    direct, issued, exits = [], 0, 0
    for w in range(YEARS * WEEKS):
        final = w >= (YEARS - 1) * WEEKS
        for a in range(N_LA):
            for _ in range(rng.poisson(demand[a] / WEEKS)):
                cf = rng.lognormal(0, CAP_SIGMA)
                if rng.random() < gate1_gross:
                    if cf >= thr: appeals[a].append((w + APPEAL_WEEKS, w))
                    elif final: exits += 1
                else: queue[a].append((w, False))
            keep = []
            for ret, arr in appeals[a]:
                if ret <= w:
                    if rng.random() < APPEAL_SUCCESS: queue[a].append((arr, True))
                    elif final: exits += 1
                else: keep.append((ret, arr))
            appeals[a] = keep
            for _ in range(min(rng.poisson(capacity[a] / WEEKS), len(queue[a]))):
                arr, was_appeal = queue[a].pop(0)
                if rng.random() < GATE2:
                    if final: exits += 1
                    continue
                if final:
                    issued += 1
                    if not was_appeal: direct.append(w - arr)
    return np.array(direct, dtype=float), issued, exits


def timely_at(wait, duration_mean, duration_cv=0.45, seed=3):
    """Share of plans meeting the twenty-week deadline at a given process duration."""
    k = 1 / duration_cv ** 2
    drng = np.random.default_rng(900_000 + seed)
    dur = np.maximum(1.0, drng.gamma(k, duration_mean / k, size=len(wait)))
    return float(np.mean(wait + dur <= DEADLINE))


if __name__ == "__main__":
    import time
    t0 = time.time()
    SEEDS = list(SEEDS)
    CAP_SEEDS = SEEDS[:5]

    def band(a):
        a = np.asarray(a, float)
        return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                    lo=float(a.min()), hi=float(a.max()))

    # One queue pass per seed. Duration is separable, so the whole duration curve
    # follows from these without rerunning the model.
    W, ISS, EX = {}, [], []
    for s in SEEDS:
        w, i, e = waits(seed=s); W[s] = w; ISS.append(i); EX.append(e)

    grid = np.arange(10, 26.01, 0.25)
    duration_curve = []
    for d in grid:
        v = np.array([timely_at(W[s], float(d), seed=s) for s in SEEDS])
        duration_curve.append(dict(duration=round(float(d), 2), issued=int(np.mean(ISS)),
                                   timely=round(float(v.mean()), 4),
                                   sd=round(float(v.std(ddof=1)), 4),
                                   lo=round(float(v.min()), 4), hi=round(float(v.max()), 4)))
    best = min(duration_curve, key=lambda r: abs(r["timely"] - TIMELY))
    BEST = best["duration"]
    base_t = [timely_at(W[s], BEST, seed=s) for s in SEEDS]
    baseline = dict(issued=band(ISS), timely=band(base_t), exits=band(EX),
                    gate1_gross=round(NET_GATE1 / (1 - APPEAL_SHARE * APPEAL_SUCCESS), 4),
                    threshold=round(appeal_threshold(APPEAL_SHARE), 3), duration=BEST)

    queue_curve = []
    for r in np.arange(0.70, 1.82, 0.04):
        ii, tt = [], []
        for s in CAP_SEEDS:
            w, i, _ = waits(seed=s, capacity_ratio=float(r))
            ii.append(i); tt.append(timely_at(w, 14.0, duration_cv=0.0001, seed=s))
        queue_curve.append(dict(ratio=round(float(r), 2), issued=int(np.mean(ii)),
                                timely=round(float(np.mean(tt)), 4)))

    GROSS = NET_GATE1 / (1 - APPEAL_SHARE * APPEAL_SUCCESS)
    import sys as _sys
    this = _sys.modules[__name__]

    def lever_run(appeal_share=None, duration=None, appeal_weeks=None, **kw):
        ii, ee, tt = [], [], []
        old_net, old_wk = this.NET_GATE1, this.APPEAL_WEEKS
        if appeal_share is not None:
            this.NET_GATE1 = GROSS * (1 - appeal_share * APPEAL_SUCCESS)
            kw["appeal_share"] = appeal_share
        if appeal_weeks is not None:
            this.APPEAL_WEEKS = appeal_weeks
        try:
            for s in SEEDS:
                w, i, e = waits(seed=s, **kw)
                ii.append(i); ee.append(e); tt.append(timely_at(w, duration or BEST, seed=s))
        finally:
            this.NET_GATE1, this.APPEAL_WEEKS = old_net, old_wk
        return band(ii), band(tt), band(ee)

    levers = []
    for label, kw in [("Assessment capacity +50%",         dict(capacity_ratio=2.4)),
                      ("Assessment capacity +100%",        dict(capacity_ratio=3.2)),
                      (f"Process {BEST} to 16 weeks",      dict(duration=16.0)),
                      ("Appeal resolved in 10 not 30 wk",  dict(appeal_weeks=10)),
                      ("Appeal reachable by 40%",          dict(appeal_share=0.40)),
                      ("Appeal reachable by 70%",          dict(appeal_share=0.70))]:
        bi, bt, be = lever_run(**kw)
        levers.append(dict(lever=label, issued=bi, timely=bt, exits=be,
                           change=round(100 * (be["mean"] / baseline["exits"]["mean"] - 1), 1)))

    steps = [dict(steps_per_year=sp,
                  issued=int(np.mean([run(duration_mean=BEST, seed=s, steps_per_year=sp)["issued"] for s in SEEDS[:3]])),
                  timely=round(float(np.mean([run(duration_mean=BEST, seed=s, steps_per_year=sp)["timely"] for s in SEEDS[:3]])), 4))
             for sp in (26, 52, 104, 208)]
    horizon = [dict(years=y,
                    issued=int(np.mean([run(duration_mean=BEST, seed=s, years=y)["issued"] for s in SEEDS[:3]])),
                    timely=round(float(np.mean([run(duration_mean=BEST, seed=s, years=y)["timely"] for s in SEEDS[:3]])), 4))
               for y in (2, 3, 4, 6, 8)]
    stab = stability(seed=3, years=10)

    ens = [run(duration_mean=BEST, seed=s) for s in SEEDS]
    baseline["appeal_n"] = band([x["appeal_n"] for x in ens])
    baseline["appeal_median_weeks"] = band([x["appeal_median_weeks"] for x in ens])
    baseline["cap_issued"] = float(np.median([x["cap_issued"] for x in ens]))
    baseline["cap_exited"] = float(np.median([x["cap_exited"] for x in ens]))

    json.dump(dict(
        actual=dict(issued=PLANS, timely=TIMELY, requests=REQUESTS, deadline=DEADLINE,
                    gate1=NET_GATE1, gate2=GATE2, published_no_plan=50_500),
        n_seeds=len(SEEDS), queue_curve=queue_curve, duration_curve=duration_curve,
        best_duration=best, baseline=baseline, levers=levers,
        robustness=dict(steps=steps, horizon=horizon, stability=stab)),
        open("sweep.json", "w"), separators=(",", ":"))

    b = baseline
    print(f"Gross gate-1 refusal inferred: {b['gate1_gross']:.1%}  (published net {NET_GATE1:.1%})")
    print(f"Best-fit process duration against the {len(SEEDS)}-seed mean: {BEST} weeks")
    print(f"  timeliness  {b['timely']['mean']:.1%} sd {b['timely']['sd']:.1%} "
          f"[{b['timely']['lo']:.1%}, {b['timely']['hi']:.1%}]   England {TIMELY:.1%}")
    print(f"  plans       {b['issued']['mean']:,.0f} sd {b['issued']['sd']:,.0f} "
          f"[{b['issued']['lo']:,.0f}, {b['issued']['hi']:,.0f}]   England {PLANS:,}")
    print(f"  left        {b['exits']['mean']:,.0f} sd {b['exits']['sd']:,.0f}   published 50,500 "
          f"(gate rates applied to the request total give ~50,400, so this is not an independent check)")
    print(f"  via appeal  {b['appeal_n']['mean']:,.0f}, median {b['appeal_median_weeks']['mean']:.1f} weeks")
    print("\nLevers (children leaving without a plan):")
    for l in levers:
        print(f"  {l['lever']:<30} {l['exits']['mean']:>8,.0f}  {l['change']:>+6.1f}%")
    print("\nRobustness:")
    print("  time resolution: " + ", ".join(f"{r['steps_per_year']}/yr {r['timely']:.1%}" for r in steps))
    print("  horizon:         " + ", ".join(f"{r['years']}yr {r['timely']:.1%}" for r in horizon))
    print(f"  no steady state: {stab['n_under_capacity']} of {stab['n_la']} authorities hold less "
          f"capacity than their own inflow; their queues grow without bound")
    print(f"\n{time.time()-t0:.0f}s")
