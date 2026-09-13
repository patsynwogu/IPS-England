"""
IPS-England v1.3 -- agent-based simulation of the SEND identification and assessment
pathway in England.

AGENTS
  Family agents hold a navigational capacity drawn from a lognormal distribution. On
  refusal at either statutory gate they decide whether to appeal. Appeal costs time and
  succeeds with high probability, so it is a rational choice that is unequally available.

  Authority agents screen incoming requests, assess at their own capacity, and raise their
  refusal propensity as their own backlog grows. Successful appeals return to their queue,
  which raises backlog further and closes the loop.

TWO STATUTORY GATES, both measured
  Gate 1, refused progression to assessment: 43,300 of 162,700 requests in 2025 (26.6%)
  Gate 2, assessed but no plan issued: 7,200 of 118,800 assessments in 2025 (6.0%)
  Plans issued 2025: 111,200. Calibration target used here: 110,708.

The published 26.6% is the outcome after appeals have resolved, so the model infers the
gross refusal rate whose post-appeal residue equals it. At an 18% appeal rate that gross
figure is 32.4%.

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
        pressure_beta=0.0, cap_sigma=CAP_SIGMA, seed=3):
    gate1_gross = NET_GATE1 / (1 - appeal_share * APPEAL_SUCCESS)
    thr = appeal_threshold(appeal_share, cap_sigma)
    rng = np.random.default_rng(seed)

    share = rng.lognormal(0, 0.65, N_LA); share /= share.sum()
    demand = share * REQUESTS
    capacity = share * PLANS * rng.lognormal(np.log(capacity_ratio), 0.45, N_LA)
    k = 1 / duration_cv ** 2

    queue = [[] for _ in range(N_LA)]
    appeals = [[] for _ in range(N_LA)]
    direct, via_appeal = [], []
    issued = exits = appealed = 0
    cap_issued, cap_exited = [], []

    for w in range(YEARS * WEEKS):
        final = w >= (YEARS - 1) * WEEKS
        for a in range(N_LA):
            pressure = len(queue[a]) / max(1.0, demand[a] / WEEKS * 8)
            g1 = float(np.clip(gate1_gross + pressure_beta * pressure, 0.0, 0.9))

            for _ in range(rng.poisson(demand[a] / WEEKS)):
                cf = rng.lognormal(0, cap_sigma)
                if rng.random() < g1:
                    if cf >= thr:
                        if final: appealed += 1
                        appeals[a].append((w + appeal_weeks, w, cf))
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

            for _ in range(min(rng.poisson(capacity[a] / WEEKS), len(queue[a]))):
                arr, cf, was_appeal = queue[a].pop(0)
                if rng.random() < GATE2:
                    if final: exits += 1; cap_exited.append(cf)
                    continue
                dur = max(1, rng.gamma(k, duration_mean / k))
                if final:
                    t = (w - arr) + dur
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


if __name__ == "__main__":
    queue_curve = []
    for r in np.arange(0.70, 1.82, 0.04):
        x = run(capacity_ratio=float(r), duration_mean=14.0, duration_cv=0.0001)
        queue_curve.append(dict(ratio=round(float(r), 2), issued=x["issued"],
                                timely=round(x["timely"], 4), exits=x["exits"]))

    duration_curve = []
    for d in np.arange(10, 26.5, 0.5):
        x = run(duration_mean=float(d))
        duration_curve.append(dict(duration=round(float(d), 1), issued=x["issued"],
                                   timely=round(x["timely"], 4), exits=x["exits"]))

    best = min(duration_curve, key=lambda r: abs(r["timely"] - TIMELY))
    base = run(duration_mean=best["duration"])

    # Counterfactuals. The baseline holds NET refusal at the published 26.6%, which pins
    # the exit population by construction. A counterfactual on appeal access therefore has
    # to hold the GROSS rate fixed and let the net fall, otherwise nothing can move.
    GROSS = NET_GATE1 / (1 - APPEAL_SHARE * APPEAL_SUCCESS)
    import sys
    this = sys.modules[__name__]

    def counterfactual(appeal_share=None, **kw):
        args = dict(duration_mean=best["duration"]); args.update(kw)
        if appeal_share is None:
            return run(**args)
        old = this.NET_GATE1
        this.NET_GATE1 = GROSS * (1 - appeal_share * APPEAL_SUCCESS)
        try:     return run(appeal_share=appeal_share, **args)
        finally: this.NET_GATE1 = old

    levers = []
    for label, kw in [("Assessment capacity +50%",        dict(capacity_ratio=2.4)),
                      ("Assessment capacity +100%",       dict(capacity_ratio=3.2)),
                      ("Process 21 to 16 weeks",          dict(duration_mean=16.0)),
                      ("Appeal resolved in 10 not 30 wk", dict(appeal_weeks=10)),
                      ("Appeal reachable by 40%",         dict(appeal_share=0.40)),
                      ("Appeal reachable by 70%",         dict(appeal_share=0.70))]:
        x = counterfactual(**kw)
        levers.append(dict(lever=label, issued=x["issued"], timely=round(x["timely"], 4),
                           exits=x["exits"], change=round(100 * (x["exits"] / base["exits"] - 1), 1)))

    json.dump(dict(
        actual=dict(issued=PLANS, timely=TIMELY, requests=REQUESTS, deadline=DEADLINE,
                    gate1=NET_GATE1, gate2=GATE2, published_no_plan=50_500),
        queue_curve=queue_curve,
        duration_curve=duration_curve,
        best_duration=best,
        baseline=dict(issued=base["issued"], timely=round(base["timely"], 4),
                      appeal_n=base["appeal_n"],
                      appeal_median_weeks=round(base["appeal_median_weeks"], 1),
                      exits=base["exits"],
                      cap_issued=round(base["cap_issued"], 2),
                      cap_exited=round(base["cap_exited"], 2),
                      gate1_gross=round(base["gate1_gross"], 4),
                      threshold=round(base["threshold"], 3)),
        levers=levers,
    ), open("sweep.json", "w"), separators=(",", ":"))

    print(f"Gross gate-1 refusal inferred: {base['gate1_gross']:.1%}  (published net {NET_GATE1:.1%})")
    print(f"Best-fit process duration: {best['duration']} weeks -> {best['timely']:.1%} timely "
          f"(England {TIMELY:.1%}), {best['issued']:,} plans (England {PLANS:,})")
    print(f"Reached a plan only by appealing: {base['appeal_n']:,}, median {base['appeal_median_weeks']:.0f} weeks")
    print(f"Left the pathway without a plan:  {base['exits']:,}  (published 50,500)")
    print(f"Median navigational capacity: plan {base['cap_issued']:.2f}, left {base['cap_exited']:.2f}")
    print("\nLevers:")
    for l in levers:
        print(f"  {l['lever']:<28} issued {l['issued']:>8,}  timely {l['timely']:>6.1%}  "
              f"left {l['exits']:>7,}  {l['change']:>+6.1f}%")
