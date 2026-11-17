"""Forecast a launch day's Twitch concurrent viewers, hour by hour.

Model v2 (calibrated on the case's own comparables at run time, pure stdlib):

  For each past big launch, take its release-day hourly Twitch category
  counts and form the log-ratio of each hour h = 2..24 to that launch's
  hour-1 print.  Then, per hour, regress that log-ratio on the log of the
  launch's hour-1 print:

      log(viewers_h / viewers_1) = a_h + b_h * (log(viewers_1) - log(100000))

  v2 fits that regression TWICE per hour and blends the two centres:

  * the FULL set: v1's calibration set (19 launches after the filters
    below), and
  * the ROLLING set: the subset whose unlock is a rolling midnight-local
    release (8 launches) -- the same unlock shape as the target (GTA VI
    releases rolling midnight local, console-only) and as all four
    practice launches.

  The forecast median is 0.8 * rolling centre + 0.2 * full centre.  The
  rolling launches carry the sharp US-unlock step at hours 5-6 and the
  strong evening growth that simultaneous-global launches dilute in the
  full set; the 20% full-set weight hedges the small rolling sample (and
  keeps Spider-Man 2, whose midday dip no rolling launch predicts, from
  blowing out).  The five quantiles are the median plus the empirical
  5/25/50/75/95% quantiles of the POOLED residuals (rolling-set residuals
  against the rolling fit plus full-set residuals against the full fit),
  so the spread is the honest cross-launch spread, widening with horizon.

Which comparables are used (the filters matter more than the regression):
  - the target's own pre-release category history is skipped;
  - a launch counts only if its release day was already materially live
    at 00:00 UTC (hour-1 print at least 5% of that day's maximum):
    this drops fixed-time global unlocks (a 10:00 UTC+8 or 14:00Z
    launch has a near-zero hour 1 and a meaningless ratio);
  - early-access-contaminated launches are dropped (their "release day"
    is days after the real launch, so the curve is post-launch decay);
  - weak-tier launches (free-to-play, slow-burn) are dropped;
  - the rolling set additionally requires the unlock text to say
    "rolling" or "midnight local" (and not "simultaneous" / "single
    global"): simultaneous launches have no US-unlock step and a flat
    curve, so they pull the median down at hours 5-6 and in the evening.

Measured on the four practice launches (answers: SullyGnome.com hourly
Twitch category averages, the same source the kit's cases use), this
scores a pooled pinball loss of 0.1617 on the log scale, against 0.1795
for v1 and 0.3871 for the flat house baseline (see replay.py and
STRATEGY.md).  90% coverage 91% (practice) / 94% (final-like check).

Run:  python3 main.py   (reads $MAKEFUN_INPUT_DIR or /input, writes
$MAKEFUN_OUTPUT_DIR or /output, one <id>.out per <id>.in).
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a
# module shipped beside this file imports.  (This file is standalone,
# but the line keeps the entrypoint robust if it ever gains a sibling.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level (fallback spread only).
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Reference hour-1 print for the regression (100,000 viewers).
X0 = math.log(100000.0)
# Never extrapolate the log-size axis beyond the calibration range:
# smallest comparable hour-1 is ~6,400 (x = -2.75), largest ~875,000
# (x = +2.17).  A bigger launch is scored as the biggest calibrated one.
X_MIN = -2.75
X_MAX = 2.17
# A launch counts only when hour 1 is at least this share of its day max.
MIN_HOUR1_SHARE = 0.05
# Weight of the rolling-midnight fit in the blended median (0.8 rolling,
# 0.2 full set).  Tuned on the four practice launches + the final-like
# check; 0.7-0.9 all score within 0.001 of each other, 0.8 is the middle.
BLEND_ROLLING = 0.8


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round does.

    A whole number comes back as an int, so json.dumps writes 1240 where
    JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp (trailing Z allowed)."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def day_curve(comp: dict) -> dict[int, float]:
    """Release-day hourly viewers {hour 1..24: viewers} for a comparable."""
    day_start = parse_time(comp["day_start"])
    curve: dict[int, float] = {}
    for point in comp.get("hourly", []):
        hour = int((parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            curve[hour] = point["viewers"]
    return curve


def unlock_type(unlock: str) -> str:
    """'rolling' for rolling midnight-local releases, 'simul' for single
    simultaneous global unlocks, 'unknown' otherwise (unverified text)."""
    u = (unlock or "").lower()
    if "simultaneous" in u or "single global" in u:
        return "simul"
    if "rolling" in u or "midnight local" in u:
        return "rolling"
    return "unknown"


def select_comparables(case: dict) -> list[dict[int, float]]:
    """The calibration set: past launches whose release-day shape is a
    fair analogue of a rolling-midnight console launch.

    Drops, in order: the target's own pre-release history, the case's own
    launch (by name), launches not yet live at 00:00 UTC (hour 1 below
    5% of the day's maximum: fixed-time global unlocks), launches whose
    release day was contaminated by early access, and weak-tier launches.
    """
    own_name = case.get("game", {}).get("name", "")
    chosen: list[dict[int, float]] = []
    for comp in sorted(case.get("comparables", []), key=lambda c: c.get("name", "")):
        unlock = comp.get("unlock", "") or ""
        name = comp.get("name", "") or ""
        if "target-history" in unlock or "Grand Theft Auto VI" in name:
            continue
        if own_name and name == own_name:
            continue
        if "early-access-contaminated" in unlock:
            continue
        if "Tier: weak" in unlock:
            continue
        curve = day_curve(comp)
        first = curve.get(1)
        if not first or first <= 0:
            continue
        peak = max(curve.values())
        if not peak or first < MIN_HOUR1_SHARE * peak:
            continue
        chosen.append(curve)
    return chosen


def select_rolling(case: dict) -> list[dict[int, float]]:
    """The rolling-midnight subset of select_comparables: launches whose
    unlock text says rolling / midnight local.  These share the target's
    unlock shape (NZ/Australia/Asia/Europe live at 00:00 UTC, the US
    unlocking at 04:00-05:00Z, evening prime time later), so their
    hour-5 step and evening growth match the target's much better than
    simultaneous-global launches do."""
    own_name = case.get("game", {}).get("name", "")
    chosen: list[dict[int, float]] = []
    for comp in sorted(case.get("comparables", []), key=lambda c: c.get("name", "")):
        unlock = comp.get("unlock", "") or ""
        name = comp.get("name", "") or ""
        if "target-history" in unlock or "Grand Theft Auto VI" in name:
            continue
        if own_name and name == own_name:
            continue
        if "early-access-contaminated" in unlock:
            continue
        if "Tier: weak" in unlock:
            continue
        if unlock_type(unlock) != "rolling":
            continue
        curve = day_curve(comp)
        first = curve.get(1)
        if not first or first <= 0:
            continue
        peak = max(curve.values())
        if not peak or first < MIN_HOUR1_SHARE * peak:
            continue
        chosen.append(curve)
    return chosen


def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, list[float]]:
    """Ordinary least squares y = a + b*x; returns (a, b, sorted residuals)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    resid = sorted(y - (a + b * x) for x, y in zip(xs, ys))
    return a, b, resid


def _quantile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolated p-quantile of an ascending list."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    pos = p * (n - 1)
    lo = int(math.floor(pos))
    hi = min(n - 1, lo + 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _fit_hour(curves: list[dict[int, float]], hour: int):
    """Per-hour OLS of log(viewers_h / viewers_1) on log(viewers_1) for one
    set of curves.  Returns (intercept, slope, sorted residuals) or None
    when the hour has no usable points."""
    xs: list[float] = []
    ys: list[float] = []
    for curve in curves:
        first = curve.get(1)
        value = curve.get(hour)
        if first and first > 0 and value and value > 0:
            xs.append(math.log(first) - X0)
            ys.append(math.log(value / first))
    if len(xs) >= 3:
        return _ols(xs, ys)
    if xs:
        med = _quantile(sorted(ys), 0.5)
        return (med, 0.0, sorted(y - med for y in ys))
    return None


def forecast_case(case: dict) -> dict:
    """Forecast hours 2..24 of one case as {"hours": [{"hour", "q"}, ...]}."""
    if case.get("levels", LEVELS) != LEVELS:
        raise ValueError(f"levels {case.get('levels')} are not {LEVELS}")
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first is None:
        raise ValueError("no hour-1 print in known")
    p1 = max(1.0, float(first["viewers"]))
    x = max(X_MIN, min(X_MAX, math.log(p1) - X0))
    full = select_comparables(case)
    rolling = select_rolling(case)
    # Emit the requested hours in ascending order, whatever order the
    # case lists them in; an empty forecast list means hours 2..24.
    requested = {row["hour"] for row in case.get("forecast", [])} or set(range(2, 25))
    rows = []
    for hour in sorted(h for h in requested if 2 <= h <= 24):
        ffit = _fit_hour(full, hour)
        rfit = _fit_hour(rolling, hour)
        if ffit is None and rfit is None:
            # No calibration data for this hour: flat median, baseline spread.
            centre, offsets = 0.0, [Z[i] * 0.15 * math.sqrt(hour - 1) for i in range(5)]
        else:
            if rfit is None:
                centre = ffit[0] + ffit[1] * x
                resid = ffit[2]
            elif ffit is None:
                centre = rfit[0] + rfit[1] * x
                resid = rfit[2]
            else:
                centre = (BLEND_ROLLING * (rfit[0] + rfit[1] * x)
                          + (1.0 - BLEND_ROLLING) * (ffit[0] + ffit[1] * x))
                # Pooled residuals: rolling residuals against the rolling
                # fit plus full-set residuals against the full fit.  The
                # pooled spread (n up to 27) is stabler than the rolling
                # set's own (n = 8) and keeps 90% coverage near 0.90.
                resid = sorted(rfit[2] + ffit[2])
            if len(resid) >= 5:
                offsets = [_quantile(resid, tau) for tau in LEVELS]
            else:
                sd = math.sqrt(sum(r * r for r in resid) / max(1, len(resid) - 1)) if len(resid) > 1 else 0.30
                offsets = [z * max(sd, 0.30) for z in Z]
        quantiles: list[float | int] = []
        prev = 0.0
        for off in offsets:
            value = round2(p1 * math.exp(centre + off))
            value = max(1.0, min(1_000_000_000.0, float(value)))
            value = max(value, prev)  # quantiles must be non-decreasing
            quantiles.append(value)
            prev = value
        rows.append({"hour": hour, "q": quantiles})
    return {"hours": rows}


def baseline_forecast(case: dict) -> dict:
    """The house baseline: every hour stays at hour 1, spread widening
    like a random walk.  Only used when the calibrated forecast fails."""
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    p1 = max(1.0, float(first["viewers"])) if first else 1.0
    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        rows.append(
            {
                "hour": hour,
                "q": [round2(p1 * math.exp(z * 0.15 * math.sqrt(hour - 1))) for z in Z],
            }
        )
    return {"hours": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            forecast = forecast_case(case)
        except Exception:
            # Never crash a case: an invalid case scores as flat and takes
            # no prize, while the baseline forecast stays valid.
            forecast = baseline_forecast(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
