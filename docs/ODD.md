# IPS-England v1.5: ODD Protocol

**Model:** IPS-England, an agent-based model of the special educational needs identification and assessment pathway in England
**Version described:** v1.5 (`model.py` in https://github.com/patsynwogu/IPS-England)
**Author:** Patsy Nwogu (ORCID 0009-0005-2524-4559)
**Archived data and outputs:** https://doi.org/10.7910/DVN/NAFBST
**Protocol:** This description follows the ODD protocol (Overview, Design concepts, Details) as updated by Grimm et al. (2020).

---

## 1. Purpose and patterns

### 1.1 Purpose

IPS-England tests whether the two defining features of England's Education, Health and Care (EHC) plan system, the volume of plans issued and the delay in issuing them, can be explained by the capacity local authorities have to carry out assessments. This is the prevailing explanation in policy debate: delay and shortfall arise because there are too few assessment staff.

The model represents the statutory route a child's request for an EHC needs assessment travels, from request to plan, and asks two questions:

1. Can any level of assessment capacity reproduce England's published plan volume and timeliness at the same time?
2. Under calibrated conditions, how much do resourcing changes (more capacity, a shorter statutory process, faster appeals) change the number of children who leave the pathway without a plan, compared with a change in how many refused families can appeal?

The model is intended for researchers and policy analysts working on SEND provision and on the design of statutory processes. It is a sufficiency test and a comparison of levers, not a forecasting tool.

### 1.2 Patterns

The model is evaluated against three patterns published for England in calendar year 2025 (Department for Education, *Education, health and care plans*, January 2026):

| Pattern | Published value |
|---|---|
| New EHC plans issued per year | 110,708 |
| Share of plans issued within the 20-week statutory deadline | 46.1% |
| Requests refused progression to assessment (net of appeals) | 43,300 of 162,702 (26.6%) |
| Assessments not resulting in a plan | 7,200 of 118,800 (6.0%) |

Plan volume and timeliness are the calibration and validation targets. The two gate rates are inputs, not targets (see Section 6).

---

## 2. Entities, state variables and scales

### 2.1 Entities

**Local authorities (152).** Each authority receives requests, applies the first statutory gate, holds its own assessment queue, assesses at its own capacity and issues plans. There is no central coordination between authorities.

| State variable | Type | Description |
|---|---|---|
| `share` | real, static | Authority's share of national demand. Drawn once per run from lognormal(0, 0.65), normalised to sum to 1. |
| `demand` | real, static | Annual requests: `share × 162,702`. |
| `capacity` | real, static | Annual assessments the authority can complete: `share × 110,708 × lognormal(ln(capacity_ratio), 0.45)`. |
| `queue` | list, dynamic | First-in, first-out queue of requests awaiting assessment. Each entry holds the request's arrival step, the family's navigational capacity, and whether it arrived via appeal. |
| `appeals` | list, dynamic | Appeals in progress, each with its return step, original arrival step and the family's navigational capacity. |

**Requests (child and family agents).** One agent is created for each request for an EHC needs assessment. The agent represents a child and the family acting on their behalf.

| State variable | Type | Description |
|---|---|---|
| `arrival` | integer | Time step at which the request was made. Retained through any appeal, so reported waits run from the original request. |
| `cf` | real | Navigational capacity: the family's ability to contest a refusal. Drawn from lognormal(0, 0.80). It stands in for everything that makes an appeal reachable (time, knowledge, confidence, support, money) and is not measured. |
| `was_appeal` | boolean | Whether the request reached the assessment queue through a successful appeal. |

**Global parameters.**

| Parameter | Value | Source or basis |
|---|---|---|
| Authorities (`N_LA`) | 152 | Number of local authorities in England with SEND responsibilities |
| Annual requests (`REQUESTS`) | 162,702 | DfE, calendar year 2025 |
| Plan volume scale (`PLANS`) | 110,708 | DfE, calendar year 2025 |
| Net gate 1 refusal (`NET_GATE1`) | 0.266 | DfE, 43,300 of 162,702 |
| Gate 2, assessed but no plan (`GATE2`) | 0.060 | DfE, 7,200 of 118,800 |
| Share of refused families who appeal (`APPEAL_SHARE`) | 0.18 | Assumption, bounded by roughly 25,000 SEND appeals registered across all grounds (Ministry of Justice, Tribunal Statistics 2024/25) |
| Appeal success rate (`APPEAL_SUCCESS`) | 0.99 | Ministry of Justice: 99% of decided cases found in favour of families |
| Appeal duration (`APPEAL_WEEKS`) | 30 weeks | Assumption |
| Capacity dispersion (`CAP_SIGMA`) | 0.80 | Assumption |
| Statutory process duration (`duration_mean`) | 20.5 weeks (calibrated) | Calibrated to timeliness, see Section 7.8 |
| Process duration variability (`duration_cv`) | 0.45 | Assumption |
| Baseline capacity ratio (`capacity_ratio`) | 1.60 | Baseline setting, see Section 7.2 |
| Backlog pressure on refusal (`pressure_beta`) | 0.0 | Implemented, switched off in every reported result |
| Statutory deadline (`DEADLINE`) | 20 weeks | Children and Families Act 2014 and SEND Regulations 2014 |

### 2.2 Scales

- **Time:** one step is one week (52 steps per year). The step length can be varied for the time-resolution check (26, 52, 104 or 208 steps per year).
- **Horizon:** four years per run. Years one to three are warm-up. All reported quantities come from year four.
- **Space:** not represented. Authorities are distinguished by demand and capacity only.
- **Population scale:** one agent per request, at the national scale of about 162,700 requests a year. No rescaling is applied.

---

## 3. Process overview and scheduling

Each time step, every authority is processed in index order. Within an authority, four processes run in this order:

1. **Refusal propensity.** The authority's probability of refusing at gate 1 is set. With `pressure_beta = 0` (all reported results) it equals the gross gate 1 rate, 32.4%.
2. **Arrivals and gate 1.** New requests arrive. Each is refused or accepted into the assessment queue. Refused families with enough navigational capacity lodge an appeal. The rest leave the pathway.
3. **Appeal resolution.** Appeals that have reached their return step are decided. Successful appeals rejoin the authority's assessment queue with their original arrival time. Unsuccessful appeals leave the pathway.
4. **Assessment and gate 2.** The authority assesses as many queued requests as its capacity allows that week, oldest first. Each assessed request either produces no plan (gate 2) or produces a plan after the statutory process.

State variables are updated immediately (asynchronous updating within an authority). Authorities do not interact directly, so the order in which they are processed does not affect results. Successful appeals compete with new requests for the same assessment capacity, which is the model's feedback loop.

Outcomes are recorded only in the final year: plans issued, time from request to plan, route (direct or via appeal), and exits from the pathway.

---

## 4. Design concepts

**Basic principles.** The model combines a queueing representation of assessment capacity with the fixed sequence the law requires: a decision on whether to assess, then professional advice, drafting, consultation and issue. The core idea is a sufficiency test (a generative explanation in the sense of Epstein): if the resourcing account is right, some capacity setting should reproduce both England's volume and its timeliness. The second principle is contestability. A published refusal rate is the result after appeals, so it hides a larger gross refusal rate and an unequal ability to challenge it.

**Emergence.** National plan volume, timeliness, the number of children leaving without a plan, and divergence between authorities all emerge from heterogeneous authority capacity, individual appeal decisions, and appeals returning to the queue. The gate rates and the process duration distribution are imposed.

**Adaptation.** Families make one decision: whether to appeal a refusal. They appeal if their navigational capacity is at or above a threshold (Section 7.3). Authorities could raise their refusal rate as their backlog grows (`pressure_beta`), but this is switched off in all reported results.

**Objectives.** Agents do not optimise. The appeal rule is a threshold rule, not an explicit utility calculation.

**Learning.** None.

**Prediction.** None.

**Sensing.** Families know their own navigational capacity. With `pressure_beta` switched on, an authority would sense its own backlog. Nothing senses other agents' states.

**Interaction.** Indirect only, through the shared assessment queue. Children whose appeals succeed rejoin the same queue as new requests and take up capacity. There is no direct interaction between children or between authorities.

**Stochasticity.** Authority demand shares and capacities, request arrivals (Poisson), families' navigational capacity (lognormal), gate 1 and gate 2 outcomes (Bernoulli), appeal outcomes (Bernoulli), weekly assessment throughput (Poisson) and statutory process duration (gamma) are all random. Process duration is drawn from a separate random number generator (seed `900000 + seed`) from everything else (seed `seed`). As a result, changing the process duration leaves every queueing decision in a run identical, and the effect of duration can be isolated exactly.

**Collectives.** None. Authorities are containers for queues, not collectives of agents.

**Observation.** In the final year of each run the model records: plans issued; timeliness, meaning the share of plans reached directly (not via appeal) with total time from request to plan within 20 weeks; the number of children leaving without a plan; the number and median duration of plans reached via appeal; and the median navigational capacity of children who received a plan and of those who left. Every reported figure is the mean across ten seeds (1 to 10), reported with standard deviation and range.

---

## 5. Initialisation

At the start of each run:

1. Each authority's demand share is drawn from lognormal(0, 0.65) and normalised across the 152 authorities.
2. Each authority's annual demand is set to `share × 162,702`, and annual capacity to `share × 110,708 × lognormal(ln(capacity_ratio), 0.45)`.
3. All queues and appeal lists are empty.
4. The gross gate 1 refusal rate and the appeal threshold are computed from the parameters (Sections 7.1 and 7.3).

Initialisation differs between seeds only through the random draws. The first three years act as warm-up so that queues are populated before any outcome is recorded.

---

## 6. Input data

The model uses no time-series input during a run. Published figures enter as fixed parameters or as calibration and validation targets:

- **Department for Education (2026), *Education, health and care plans*, January 2026 (calendar year 2025):** 162,702 requests; 110,708 new plans; 46.1% issued within 20 weeks excluding statutory exceptions; 43,300 refused progression to assessment; 7,200 assessments producing no plan.
- **Ministry of Justice (2025), *Tribunal Statistics*, 2024/25:** roughly 25,000 SEND appeals registered across all grounds; 99% of decided cases found in favour of families.

---

## 7. Submodels

### 7.1 Gross gate 1 refusal

The published refusal rate (26.6%) is the rate after appeals have resolved. The model infers the gross rate whose post-appeal residue equals it:

```
gate1_gross = NET_GATE1 / (1 − APPEAL_SHARE × APPEAL_SUCCESS)
            = 0.266 / (1 − 0.18 × 0.99)
            = 0.324
```

### 7.2 Authority demand and capacity

Demand shares and capacity multipliers are lognormal, standing in for the spread between authorities until per-authority DfE data is incorporated. `capacity_ratio` scales capacity relative to plan volume. The baseline is 1.60. The capacity levers set it to 2.4 (+50%) and 3.2 (+100%).

### 7.3 Appeal decision

Each refused family appeals if its navigational capacity `cf` is at or above a threshold `θ`. The threshold is chosen so that the intended share of families qualify:

```
θ = exp(CAP_SIGMA × Φ⁻¹(1 − APPEAL_SHARE))
```

where Φ⁻¹ is the inverse standard normal (computed by bisection). With `APPEAL_SHARE = 0.18` and `CAP_SIGMA = 0.80`, 18% of refused families appeal.

### 7.4 Arrivals and gate 1

Each week, authority `a` receives `Poisson(demand_a / steps_per_year)` requests. Each request draws `cf ~ lognormal(0, 0.80)` and is refused with probability `g1`:

```
g1 = clip(gate1_gross + pressure_beta × pressure_a, 0, 0.9)
pressure_a = queue length / max(1, 8 weeks of demand)
```

With `pressure_beta = 0`, `g1 = gate1_gross`. A refused request with `cf ≥ θ` becomes an appeal returning after `APPEAL_WEEKS`. Otherwise the child leaves the pathway. Accepted requests join the back of the queue.

### 7.5 Appeals

When an appeal reaches its return step it succeeds with probability 0.99. A successful appeal rejoins the queue with its original arrival step and `was_appeal = True`. An unsuccessful appeal leaves the pathway.

### 7.6 Assessment and gate 2

Each week the authority assesses `min(Poisson(capacity_a / steps_per_year), queue length)` requests, oldest first. Each assessment produces no plan with probability 0.06 (the child leaves the pathway). Otherwise a plan is issued after the statutory process.

### 7.7 Statutory process duration and time to plan

The duration of the statutory sequence is drawn from a gamma distribution with mean `duration_mean` and coefficient of variation 0.45 (shape `k = 1 / 0.45²`), with a minimum of one week. It is drawn from the separate duration generator. Total time from request to plan is:

```
t = (current step − arrival step) × weeks per step + duration
```

A plan counts as timely if `t ≤ 20` weeks. Timeliness is measured over plans reached directly, not via appeal.

### 7.8 Calibration

Because process duration is independent of every queueing decision, queue waits are computed once per seed (function `waits`) and duration is added afterwards (function `timely_at`). This makes the timeliness curve exact rather than noisy. `duration_mean` is swept from 10 to 26 weeks in steps of 0.25. The value whose ten-seed mean timeliness is closest to England's 46.1% is selected: **20.5 weeks**.

### 7.9 Capacity sweep

To test the resourcing explanation, `capacity_ratio` is swept from 0.70 to 1.82 in steps of 0.04, with the statutory process fixed at 14 weeks and almost no variability, averaged over five seeds. This isolates what capacity alone can explain.

### 7.10 Levers

Each lever changes one parameter from the calibrated baseline and is run over ten seeds. The outcome is the change in the number of children leaving without a plan.

| Lever | Implementation |
|---|---|
| Assessment capacity +50% | `capacity_ratio = 2.4` |
| Assessment capacity +100% | `capacity_ratio = 3.2` |
| Process 20.5 to 16 weeks | `duration_mean = 16` |
| Appeals resolved in 10 weeks, not 30 | `APPEAL_WEEKS = 10` |
| Appeal reachable by 40% of refused families | `APPEAL_SHARE = 0.40`, with the gross refusal rate held constant |
| Appeal reachable by 70% of refused families | `APPEAL_SHARE = 0.70`, with the gross refusal rate held constant |

### 7.11 Stability check

The function `stability` runs one seed for ten years and records each year's end-of-year queue, split by whether an authority's capacity can clear its own inflow (`capacity ≥ inflow`, where inflow includes successful appeals).

---

## 8. Results summary (ten-seed means)

| Quantity | Model | England |
|---|---|---|
| Calibrated statutory process duration | 20.5 weeks | 20-week deadline |
| Plans issued within 20 weeks | 45.8% (sd 2.0, range 43.5 to 49.7) | 46.1% |
| Plans issued per year | 107,952 (sd 1,015) | 110,708 |
| Children leaving without a plan | 50,081 (sd 207) | 50,500 published |
| Plans reached only by appealing | 8,492 (sd 137), median 51.4 weeks | not published |
| Gross gate 1 refusal inferred | 32.4% | 26.6% published net |

Change in children leaving without a plan, against the 50,081 baseline:

| Lever | Children leaving | Change |
|---|---|---|
| Assessment capacity +50% | 50,397 | +0.6% |
| Assessment capacity +100% | 50,577 | +1.0% |
| Process 20.5 to 16 weeks | 50,081 | 0.0% |
| Appeals resolved in 10 weeks, not 30 | 50,156 | +0.2% |
| Appeal reachable by 40% | 39,219 | −21.7% |
| Appeal reachable by 70% | 24,354 | −51.4% |

**Sufficiency test.** No capacity setting reproduces both targets. The setting that comes closest on timeliness (46.4%) issues 90,204 plans, 18.5% below England. The setting closest on volume (109,873 plans) gives 92.4% timeliness.

**Scope of the claim.** Unequal access to appeal is an input to the model, not an output. The model establishes the size of the gap between the two kinds of lever, not why appeal access is unequal. The 50,081 baseline follows closely from the published gate rates applied to the published request total (about 50,400 before any simulation), so it is not an independent validation check.

---

## 9. Verification and robustness

1. **Seed variation.** All figures are ten-seed means with standard deviation and range.
2. **Time resolution.** 26, 52, 104 and 208 steps per year give 44.8%, 45.1%, 45.4% and 45.2% timeliness, with plans issued within 0.4% of each other. Results are not an artefact of the weekly step.
3. **Horizon and steady state (failed).** Timeliness falls with horizon: 47.3% at two years, 45.7% at three, 45.1% at four, 44.3% at six and 43.9% at eight. The cause is located: 22 of 152 authorities hold less capacity than their own inflow, so their queues grow without bound, and 99% of national queue growth over ten years sits inside them. The four-year reporting point is a stated convention, not a converged value.
4. **Random stream independence (failed in v1.4, fixed in v1.5).** Process duration previously shared a generator with every queueing decision. It now has its own stream.
5. **Sensitivity of the delay argument.** The duration sweep in Section 7.8.

Four results were withdrawn during development: a high-to-low-issuing authority ratio that was Monte Carlo noise; a capacity flooring bug that stalled queues; appeal returns added on top of the published refusal rate rather than inside it; and a single-seed timeliness figure reported as a central value.

---

## 10. Known limitations

- Navigational capacity is one modelled quantity standing in for everything that makes an appeal reachable. It is not measured, and the model does not identify which families hold more or less of it.
- The share of refused families who appeal (18%) and appeal duration (30 weeks) are assumptions.
- Authority-level demand and capacity are lognormal assumptions pending the DfE per-authority release. No claim about individual authorities should be drawn from this version.
- The model addresses access to plans and delay, not outcomes for children.
- The `pressure_beta` feedback is implemented but unused. Activating it requires recalibration.

---

## 11. Software and reproduction

- **Language:** Python 3. **Dependency:** NumPy only.
- **Run:** `python3 model.py` writes `sweep.json` (about eight minutes on a laptop). The web page at https://ips-england.netlify.app displays `sweep.json` and recomputes nothing.
- **Licence:** MIT.

---

## References

Department for Education (2026). *Education, health and care plans, England: January 2026*. https://explore-education-statistics.service.gov.uk

Epstein, J. M. (1999). Agent-based computational models and generative social science. *Complexity*, 4(5), 41–60.

Gilbert, N., Ahrweiler, P., Barbrook-Johnson, P., Narasimhan, K. P., and Wilkinson, H. (2018). Computational Modelling of Public Policy: Reflections on Practice. *Journal of Artificial Societies and Social Simulation*, 21(1), 14.

Grimm, V., Railsback, S. F., Vincenot, C. E., Berger, U., Gallagher, C., DeAngelis, D. L., Edmonds, B., Ge, J., Giske, J., Groeneveld, J., Johnston, A. S. A., Milles, A., Nabe-Nielsen, J., Polhill, J. G., Radchuk, V., Rohwäder, M.-S., Stillman, R. A., Thiele, J. C., and Ayllón, D. (2020). The ODD Protocol for Describing Agent-Based and Other Simulation Models: A Second Update to Improve Clarity, Replication, and Structural Realism. *Journal of Artificial Societies and Social Simulation*, 23(2), 7.

Ministry of Justice (2025). *Tribunal Statistics Quarterly*, 2024/25. https://www.gov.uk/government/collections/tribunals-statistics
