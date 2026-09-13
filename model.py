"""
IPS-England v1.1 -- two competing accounts of assessment delay, tested against the same targets.

Account A (queue-driven): delay comes from a shortage of caseworkers. Process duration is
short relative to the 20-week deadline; lateness is waiting time before a case is picked up.

Account B (duration-driven): capacity is adequate and cases are picked up promptly, but the
statutory process itself takes close to or longer than the deadline allows.

Targets, DfE Education, health and care plans, January 2026 release:
  162,702 requests for assessment during calendar 2025
  110,708 new plans issued during calendar 2025
  46.1%   of those issued within the 20-week statutory deadline (excluding exceptions)

Python is authoritative. The web page displays sweep.json and recomputes nothing.
"""
import numpy as np, json

REQUESTS, PLANS, TIMELY = 162_702, 110_708, 0.461
CONVERSION = PLANS / REQUESTS          # 68.0% of requests become plans
WEEKS, N_LA, YEARS, DEADLINE = 52, 152, 6, 20

def run(capacity_ratio, duration_mean, duration_cv, la_sigma=0.45, seed=3):
    """One full run. Returns (plans issued in final year, share within 20 weeks, backlog)."""
    rng = np.random.default_rng(seed)
    share = rng.lognormal(0, 0.65, N_LA); share /= share.sum()
    demand = share * PLANS
    capacity = demand * rng.lognormal(np.log(capacity_ratio), la_sigma, N_LA)
    k = None if duration_cv == 0 else 1 / duration_cv**2
    queues = [[] for _ in range(N_LA)]
    elapsed, issued = [], 0
    for w in range(YEARS * WEEKS):
        final = w >= (YEARS - 1) * WEEKS
        for a in range(N_LA):
            queues[a].extend([w] * rng.poisson(demand[a] / WEEKS))
            n = min(rng.poisson(capacity[a] / WEEKS), len(queues[a]))
            for _ in range(n):
                arrived = queues[a].pop(0)
                dur = duration_mean if k is None else max(1, rng.gamma(k, duration_mean / k))
                if final:
                    elapsed.append((w - arrived) + dur); issued += 1
    e = np.array(elapsed)
    return issued, (float(np.mean(e <= DEADLINE)) if len(e) else float("nan")), sum(len(q) for q in queues)

if __name__ == "__main__":
    # Account A: short process (14 weeks, fixed), delay must come from queueing.
    queue_curve = []
    for r in np.arange(0.70, 1.64, 0.02):
        n, t, b = run(r, 14, 0.0)
        queue_curve.append(dict(ratio=round(float(r),2), issued=n, timely=round(t,4), backlog=b))

    # Account B: capacity adequate (1.6x), delay comes from process duration itself.
    duration_curve = []
    for d in np.arange(8, 27, 0.5):
        n, t, b = run(1.60, float(d), 0.45)
        duration_curve.append(dict(duration=round(float(d),1), issued=n, timely=round(t,4), backlog=b))

    # Which duration best reproduces England, given adequate capacity?
    best = min(duration_curve, key=lambda r: abs(r["timely"] - TIMELY))

    # Floor sensitivity for the rigour section.
    floor_sens = [dict(floor=f, **dict(zip(("issued","timely"), run(1.30, f, 0.0)[:2])))
                  for f in (10, 14, 18, 20, 22)]

    json.dump(dict(
        actual=dict(issued=PLANS, timely=TIMELY, requests=REQUESTS,
                    conversion=round(CONVERSION,4), deadline=DEADLINE),
        queue_curve=queue_curve,
        duration_curve=duration_curve,
        best_duration=best,
        floor_sensitivity=floor_sens,
    ), open("sweep.json","w"), separators=(",",":"))

    print(f"Account A (queueing, 14-week process): best on timeliness vs best on volume")
    bt = min(queue_curve, key=lambda r: abs(r["timely"]-TIMELY))
    bv = max(queue_curve, key=lambda r: r["issued"])
    print(f"  match timeliness -> {bt['timely']:.1%} but {bt['issued']:,} plans "
          f"({100*(bt['issued']/PLANS-1):+.1f}% vs England)")
    print(f"  match volume     -> {bv['issued']:,} plans but {bv['timely']:.1%} timely "
          f"({100*(bv['timely']-TIMELY):+.1f} pts vs England)")
    print(f"\nAccount B (adequate capacity, variable process duration):")
    print(f"  best fit at duration {best['duration']} weeks -> {best['issued']:,} plans, "
          f"{best['timely']:.1%} timely   [England: {PLANS:,}, {TIMELY:.1%}]")
    print(f"\nFloor sensitivity at ratio 1.30:")
    for f in floor_sens: print(f"  {f['floor']:>2}-week process -> {f['timely']:.1%} timely")
