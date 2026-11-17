# Strategy — GTA VI launch-day Twitch viewers forecast (v2)

## What the program does

`bot.py` (packed into `main.py` by the kit's `makefun compress`) reads one
case (`/input/<id>.in`) and writes `/output/<id>.out`: for hours 2–24 of
the release day, five quantiles (5/25/50/75/95%) of that hour's Twitch
concurrent viewers in the game's category. Pure standard library, no
network, deterministic, ~0.02 s per case.

## The model

For each past big launch in the case's `comparables`, take its release-day
hourly Twitch counts and form the log-ratio of each hour h = 2..24 to that
launch's hour-1 print. Per hour, regress that log-ratio on the log of the
launch's hour-1 print:

    log(viewers_h / viewers_1) = a_h + b_h * (log(viewers_1) - log(100000))

v2 fits that regression **twice** per hour and blends the two centres:

- **Full set** (v1's calibration set, 19 launches after the filters below).
- **Rolling set** (8 launches whose unlock is a rolling midnight-local
  release — the same unlock shape as the target and as all four practice
  launches).

The forecast median is `0.8 * rolling centre + 0.2 * full centre`. The
five quantiles are the median plus the empirical 5/25/50/75/95% quantiles
of the **pooled** residuals (rolling-set residuals against the rolling
fit plus full-set residuals against the full fit). The fit is done at run
time from the case file itself, so the final case (with all 42
comparables, including the four practice launches) is calibrated on its
own data. The log-size axis is clamped to the calibration range (hour-1
6,400–875,000) so a bigger launch is scored as the biggest calibrated
one, never extrapolated linearly.

## Why this shape

A launch-day curve is not flat. Across the comparables, hour 1 is a
midnight-UTC snapshot: only the regions already unlocked (New Zealand,
Australia, Asia, Europe, UK) are in. Viewership dips to ~0.7x in hours
3–4 (dead of night in the Americas), steps up at hours 5–6 (US East
unlock, 04:00–05:00Z), sags through the morning, then rises to an
evening peak (US daytime/evening) before easing at hours 23–24. The
slope b_h is near 0 early and about −0.3 to −0.5 late: a launch already
huge in hour 1 grows little afterwards, while a small hour-1 launch
grows several-fold. The house baseline (flat at hour 1, spread widening
as 0.15·sqrt(h−1)) misses all of this.

The v2 change: the US-unlock step and the evening growth are much bigger
for rolling-midnight launches than for simultaneous-global ones (whose
hour 1 already holds the whole world, so their curve is flat). v1's
full-set median diluted the step with simultaneous launches: on the
practice cases it under-predicted hours 5–7 by 60–90% for the three
smaller launches and the evening peak by 65–127% for Wolverine. Fitting
the rolling launches separately restores the step; the 20% full-set
weight hedges the small rolling sample (n = 8) and keeps the one
practice case no rolling launch predicts — Spider-Man 2, whose midday
dip to 0.37x at hour 12 is idiosyncratic — from blowing out further.

## Measured edge (practice cases, answers from SullyGnome.com)

Practice answers are the historical source's hourly counts for the four
practice launches (Marvel's Wolverine, Red Dead Redemption 2, God of War
Ragnarök, Marvel's Spider-Man 2), fetched once from SullyGnome's public
chart API; each case's hour-1 value matches its `.in` file exactly.
Pinball loss on the log scale, mean over 23 hours × 5 quantiles:

| case | v2 | v1 | flat baseline |
|------|------|------|---------------|
| p00 Wolverine (h1 23,357) | 0.1890 | 0.2475 | 0.7437 |
| p01 RDR2 (h1 116,550) | 0.1301 | 0.1676 | 0.2868 |
| p02 GoW Ragnarök (h1 269,517) | 0.1189 | 0.1172 | 0.2146 |
| p03 Spider-Man 2 (h1 119,087) | 0.2089 | 0.1858 | 0.3033 |
| **pooled** | **0.1617** | **0.1795** | **0.3871** |

58% below the baseline (the rules quote the baseline at "about 0.387";
this replay reproduces 0.3871, which validates the scoring code).
90% coverage on practice: 91–100% per case except p03 (78%), mean ~91%
(v1: 85%); typical median miss 17–36%. The final-like check (p00 + the
four practice launches as comparables, 42 total) gives 0.1824 (v1:
0.2496), and pooled over all four final-like cases 0.1577 (v1: 0.1767).
Run `python3 replay.py` to reproduce; `python3 tests/test_bot.py` runs
the unit tests (6/6 pass).

## Entry / exit rules (what the code does, per case)

- Entry: hour-1 print p1 from `known`; the calibration sets are selected
  from the case's comparables (see below); per-hour OLS on log-ratios,
  blended 0.8 rolling / 0.2 full.
- Exit (output): 23 rows, hours 2–24, quantiles non-decreasing,
  clamped to (0, 1e9], rounded to 2 decimals.
- Never crash a case: any failure in the calibrated forecast falls back
  to the house baseline for that case (a valid forecast always beats an
  invalid one, which scores as flat and takes no prize).

## Comparable selection (the filters matter more than the regression)

1. Skip the target's own pre-release category history (tier
   `target-history`) and the case's own launch.
2. Keep only launches already materially live at 00:00 UTC: hour-1 print
   ≥ 5% of that day's maximum. This drops fixed-time global unlocks
   (10:00 UTC+8, 14:00Z, ...) whose hour 1 is near-zero and whose
   ratios are meaningless. 8 of 37 dropped.
3. Drop early-access-contaminated launches (their "release day" is days
   after the real launch, so the curve is post-launch decay, not a
   launch day). 9 dropped; pooled loss 0.2155 → 0.1861 (v1 measurement).
4. Drop weak-tier launches (free-to-play, slow-burn). Pooled 0.1861 →
   0.1842 (normal spread) / 0.1795 (empirical spread) (v1 measurement).
5. **v2 — rolling subset:** of the 19 survivors, keep the 8 whose unlock
   text says "rolling" or "midnight local" (and not "simultaneous" /
   "single global"). Rolling-only pooled 0.1659; blended 0.8/0.2 pooled
   0.1617 with coverage 91% (rolling-only coverage 89%).

19 comparables survive the full filters; 8 survive the rolling filter.
The final case holds 42 (the 38 + the four practice launches); the same
filters select 22 full / 12 rolling there.

## Tried and dropped (v2 experiments, same 4 practice cases)

- Similarity-weighted OLS (Gaussian kernel on log hour-1, σ = 0.5–1.5):
  pooled 0.184–0.191 vs 0.1795. Helps the mid-size cases (p01 0.168 →
  0.129) but wrecks the smallest (p00 0.248 → 0.311): too few similar
  neighbours at the bottom of the range. Dropped.
- Leave-one-out residuals for the spread: pooled 0.181–0.183, coverage
  0.90–0.95. Honest intervals, but the wider spread costs more pinball
  than the coverage gains. The pooled-residual spread already lands
  coverage at 0.91. Dropped.
- Spread multiplier 1.1–1.3 on the quantile offsets: pooled 0.180–0.202.
  Widening costs pinball at every quantile; the empirical spread is
  already right-sized. Dropped.
- Smoothing (a_h, b_h) across neighbouring hours: pooled 0.182. The
  hour-5 step is sharp by nature; smoothing blurs it. Dropped.
- Hour-1 channels as a second regressor: pooled 0.191. No signal beyond
  hour-1 viewers. Dropped.
- Keeping weak-tier / early-access launches: pooled 0.186 / 0.221.
  Both filters earn their keep. Dropped.
- Raising the hour-1-share filter to 10%: pooled 0.214 (p00 0.374).
  Too few small launches left to fit the slope. Dropped.
- Shape filters on the comparables (day-peak/hour-1 ≥ 2, hour-6/hour-4
  step ≥ 1.3): pooled 0.164–0.197. The step filter alone (0.1635) is
  close to the rolling blend but its coverage is worse (0.86) and it is
  a noisier proxy for unlock type than the unlock text itself. Dropped
  in favour of the text-based rolling subset.
- Theil–Sen / LAD robust fits: pooled 0.175–0.180 (blend 0.8). OLS wins;
  the outliers are signal, not noise. Dropped.
- t-shrinkage of the per-hour slopes: pooled 0.175. Dropped.
- Blend weights 0.5–1.0 (rolling share): pooled 0.162–0.166, all within
  0.004. 0.8 chosen as the middle of the flat optimum (0.9: 0.1613,
  1.0: 0.1616); 1.0 degrades p03 further (0.220) for no real gain.
- v1's dropped list still applies: pooled median curve (no size
  conditioning) 0.2852; normal instead of empirical spread 0.1842;
  big-launches-only fit 0.2610; blending toward the six biggest
  launches' median curve 0.3081; console-only subset 0.1970.

## Expected outcomes

- Practice pooled pinball ≈ 0.16 vs house baseline 0.39, v1 0.18, and
  the live leader at 0.122 (dev standings, 17 Nov). v2 closes about a
  third of v1's gap to the leader; the remaining gap is mostly p03's
  idiosyncratic midday dip, which no comparable in the case predicts.
- The final is one case (GTA VI, hour-1 print likely far above the
  calibration range). The x-clamp keeps the median at the biggest
  calibrated launch's behaviour (evening peak ≈ 0.85–1.05× hour 1 for
  the full set, higher for the rolling set); the pooled empirical spread
  (90% band roughly ×0.4 to ×2.4 at late hours) is the honest
  uncertainty. If hour 1 comes in near the top of the calibration range
  the forecast is on familiar ground; if it is far above (e.g. 2M+),
  the median is a deliberate, conservative no-extrapolation choice.
- Main risk: the final's true shape differs from every past launch
  (GTA VI is the largest launch ever; Twitch may behave differently
  at that scale, e.g. a bigger US-unlock step or a flatter evening).
  The wide pooled spread is the hedge; the median is the best
  calibrated guess.
