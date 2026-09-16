# IPS-England v1.5

[![DOI](https://img.shields.io/badge/DOI-10.7910%2FDVN%2FNAFBST-blue)](https://doi.org/10.7910/DVN/NAFBST)

An agent-based simulation of the special educational needs identification and assessment
pathway in England, built to test whether shortfall and delay can be explained by assessment
capacity. They cannot.

**Archived dataset:** https://doi.org/10.7910/DVN/NAFBST (Harvard Dataverse)
**Live page:** https://ips-england.netlify.app

`public/index.html` is self-contained with no build step. Deploy the repo to Netlify with
`publish = "public"` and it serves as it is.

## What the model is

152 local authority agents and individual child agents moving through five stages, from an
unmet need to an Education, Health and Care plan. Families hold a navigational capacity and
decide whether to appeal when refused. Authorities screen requests, assess at their own
capacity with no central coordinator, and see successful appeals return to their queue. Weekly
time step, four-year horizon, final year reported, every published figure the mean of ten random
seeds.

A `pressure_beta` parameter that raises an authority's refusal rate with its own backlog is
implemented, defaults to zero, and is used by no reported result. Activating and recalibrating it
is a task for the next version. The agent claim here rests on heterogeneous authorities queueing
independently, on the individual appeal decision, and on the divergence between authorities in
check 2 below.

Two statutory gates, both measured against published data. 26.6% of requests refused
progression to an assessment, and 6.0% of assessments producing no plan. The published 26.6%
is the rate after appeals have resolved, so the model infers the gross rate whose post-appeal
residue equals it. At an 18% appeal rate that gross figure is 32.4%.

## The findings

England in calendar year 2025 issued 110,708 new plans against 162,702 requests, with 46.1%
issued inside the twenty-week statutory deadline.

**Funding and contestability do not do the same work.** Around 50,000 children a year are
refused support they were referred for. Doubling assessment capacity changes that population
by 1.0%. Putting an appeal within reach of seven families in ten halves it. Unequal appeal
access is a mechanism the model assumes, so the result that carries weight is the size of the
gap between the two levers rather than the existence of the second.

**The deadline is shorter than the process.** Sweeping assessment capacity across its full
plausible range produces no setting that reproduces England. Tune capacity down until
timeliness comes closest, at 46.4%, and the model issues 90,204 plans, 18.5% fewer than
England. Tune capacity up until volume comes closest, at 109,873 plans, and timeliness climbs
to 92.4%. The two targets move in opposite directions. The model comes close to England only
when the statutory sequence is allowed to average 20.5 weeks, which gives 45.8% inside the
deadline with a standard deviation of 2.0 points across seeds, against England's 46.1%.

## The hypothesis

Access to special educational needs provision in England is governed by the statutory
architecture rather than by the resources available to run it. Who is identified is determined
by which families can contest a refusal, and how long identification takes is determined by the
duration of the mandated sequence. Neither responds materially to staffing.

Three falsification tests, none of which needs this model or its author, are set out in
Section Six of the page.

## Validation, including what failed

Five checks. Two failed and both are reported on the page.

1. **Seed variation.** Version 1.4 reported a single draw that sat near the favourable end of a
   six-point spread. Every figure is now a ten-seed mean with a standard deviation.
2. **Steady state. Failed.** Timeliness falls monotonically with horizon, from 47.3% at two
   years to 43.9% at eight. The cause is located: 22 of 152 authorities hold less capacity than
   their own inflow, their queues grow without bound, and 99% of national queue growth over ten
   years sits inside them. The four-year reporting point is a stated convention, not a converged
   value, and the 2.5% volume shortfall against England is the same phenomenon.
3. **Time resolution.** 26, 52, 104 and 208 steps per year give 44.8%, 45.1%, 45.4% and 45.2%.
   Clean.
4. **Random stream independence. Failed in v1.4.** Process duration shared a generator with
   every queueing decision, so changing duration silently changed which children were refused.
   Duration now draws from its own stream, which is why the duration curve in Figure 2 is
   vertical.
5. **Sensitivity of the parameter carrying the delay argument.** Reported as Table 4.

Four results were withdrawn during development and none appears on the page: a
high-to-low-issuing authority ratio that was Monte Carlo noise, a capacity flooring bug that
stalled queues, appeal returns added on top of the published refusal rate rather than inside it,
and a single-seed timeliness figure reported as a central value.

Note on what is not a check. The model places 50,081 children a year outside a plan against a
published 50,500. Applying the two published gate rates to the published request total gives
roughly 50,400 before any simulation runs, so this is the inputs restated, not independent
corroboration. The page says so.

## Reproducing the numbers

```
pip install numpy
python3 model/model.py     # writes model/sweep.json, about 8 minutes
```

Python is authoritative. The web page displays the contents of `sweep.json` and recomputes
nothing, so the page and the model cannot drift apart.

## Sources

- DfE, *Education, health and care plans*, January 2026. Calendar year 2025: 162,702 requests,
  110,708 new plans, 46.1% within 20 weeks excluding statutory exceptions, 43,300 refused
  progression to assessment, 7,200 assessments producing no plan, 718,838 plans in force across
  all ages.
- DfE, *Special educational needs in England*, 2015/16 to 2025/26. Schools census: 538,547
  pupils with plans and 1,319,780 on SEN support in 2025/26.
- Ministry of Justice, *Tribunal Statistics*, 2024/25. Roughly 25,000 SEND appeals registered
  across all grounds, 99% of decided cases going in favour of families.

The schools census and the plans release count different populations and are not
interchangeable. The census covers school pupils. The plans release covers all ages 0 to 25
across all settings.

## Known limits

- Navigational capacity is one modelled quantity standing in for everything that makes an appeal
  reachable. It is not measured, and nothing here identifies which families hold more or less of
  it.
- The share of refused families who appeal is assumed at 18%. Published tribunal statistics
  count appeals across all grounds together.
- Appeal duration is assumed at 30 weeks.
- Authority-level caseload and capacity dispersion are lognormal assumptions pending the DfE
  per-authority release. No claim about variation between individual authorities should be drawn
  from this version. Given check 2 above, that release is the first thing this model needs.
- The recognition stage is calibrated to the national trend and its absolute level is an
  assumption.
- The model addresses access and delay, not outcome.

## How to cite

> Nwogu, Patsy, 2026, *IPS-England: Simulating England's SEND Identification and Assessment
> Process*, https://doi.org/10.7910/DVN/NAFBST, Harvard Dataverse.

Check this against the citation string shown on the Dataverse landing page and use that one if
the title differs.

Patsy Nwogu · ORCID 0009-0005-2524-4559
