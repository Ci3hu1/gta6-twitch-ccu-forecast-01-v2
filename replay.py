"""Local validation: run bot.py on the four practice cases and report
pinball loss (log scale) against the flat house baseline.

Usage:  python3 replay.py

Answers: tests/practice_answers.json (SullyGnome.com hourly Twitch
category averages; each case's hour-1 value matches its .in file).

Also builds a "final-like" case -- p00's case plus the four practice
launches added as comparables, as the final case holds all 42 -- and
checks the runtime fit still behaves (same loss band, sane forecast).
"""

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
KIT_INPUT = Path.home() / "workspace/tools/makefun/gta6-twitch-ccu-forecast-01-kit/input"
sys.path.insert(0, str(REPO))
import bot  # noqa: E402

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
ANSWERS = json.loads((REPO / "tests/practice_answers.json").read_text())


def pinball(y, q, tau):
    d = math.log(max(y, 1.0)) - math.log(q)
    return 2 * max(tau * d, (tau - 1) * d)


def score(forecast, answers):
    total, n = 0.0, 0
    by_hour = {r["hour"]: r["q"] for r in forecast["hours"]}
    for hour, y in answers.items():
        if hour == 1:
            continue
        for tau, q in zip(LEVELS, by_hour[hour]):
            total += pinball(y, q, tau)
            n += 1
    return total / n


def main():
    print(f"{'case':6s} {'model':>8s} {'baseline':>9s} {'coverage':>8s} {'typ.miss':>8s}")
    pooled_m, pooled_b = 0.0, 0.0
    for pid in ("p00", "p01", "p02", "p03"):
        case = json.loads((KIT_INPUT / f"{pid}.in").read_text())
        answers = {int(h): v for h, v in ANSWERS[pid].items()}
        fc = bot.forecast_case(case)
        base = bot.baseline_forecast(case)
        m, b = score(fc, answers), score(base, answers)
        by_hour = {r["hour"]: r["q"] for r in fc["hours"]}
        cov = sum(1 for h in range(2, 25) if by_hour[h][0] <= answers[h] <= by_hour[h][4]) / 23
        miss = sum(abs(math.log(answers[h] / by_hour[h][2])) for h in range(2, 25)) / 23
        print(f"{pid:6s} {m:8.4f} {b:9.4f} {cov:7.0%} {100 * (math.exp(miss) - 1):7.1f}%")
        pooled_m += m
        pooled_b += b
    print(f"{'POOLED':6s} {pooled_m / 4:8.4f} {pooled_b / 4:9.4f}")
    print(f"improvement over baseline: {(1 - pooled_m / pooled_b) * 100:.1f}%")

    # Final-like check: p00 + the four practice launches as comparables.
    print("\nFinal-like case (p00 + 4 practice launches as comparables):")
    case = json.loads((KIT_INPUT / "p00.in").read_text())
    names = {"p00": "Marvel's Wolverine", "p01": "Red Dead Redemption 2",
             "p02": "God of War Ragnarök", "p03": "Marvel's Spider-Man 2"}
    days = {"p00": "2026-09-15T00:00:00Z", "p01": "2018-10-26T00:00:00Z",
            "p02": "2022-11-09T00:00:00Z", "p03": "2023-10-20T00:00:00Z"}
    for pid in ("p00", "p01", "p02", "p03"):
        hourly = [{"from": f"{days[pid][:11]}{h - 1:02d}:00:00Z",
                   "viewers": ANSWERS[pid][str(h)], "channels": None}
                  for h in range(1, 25)]
        case["comparables"].append({
            "name": names[pid], "day_start": days[pid],
            "unlock": "Consoles midnight local (rolling)",
            "platforms": "PS5", "source": "SullyGnome.com",
            "hourly": hourly,
        })
    fc = bot.forecast_case(case)
    answers = {int(h): v for h, v in ANSWERS["p00"].items()}
    print(f"  p00 loss with 42 comparables: {score(fc, answers):.4f} (was "
          f"{score(bot.forecast_case(json.loads((KIT_INPUT / 'p00.in').read_text())), answers):.4f})")
    print(f"  comparables selected: {len(bot.select_comparables(case))} "
          f"(of {len(case['comparables'])})")
    print("  median ratios:", " ".join(
        f"h{h}={fc['hours'][h - 2]['q'][2] / case['known'][0]['viewers']:.2f}"
        for h in (2, 6, 12, 18, 20, 24)))

    # End-to-end: run the program as the grader does, twice, compare bytes.
    with tempfile.TemporaryDirectory() as tmp:
        outs = []
        for i in (1, 2):
            outdir = Path(tmp) / f"out{i}"
            env = {"MAKEFUN_INPUT_DIR": str(KIT_INPUT),
                   "MAKEFUN_OUTPUT_DIR": str(outdir), "PATH": "/usr/bin:/bin"}
            proc = subprocess.run([sys.executable, str(REPO / "bot.py")],
                                  env=env, capture_output=True, text=True, timeout=30)
            assert proc.returncode == 0, proc.stderr
            outs.append({p.name: p.read_bytes() for p in outdir.glob("*.out")})
        assert outs[0] == outs[1], "non-deterministic output"
        print("\nEnd-to-end: 4 cases run, outputs byte-identical across two runs.")


if __name__ == "__main__":
    main()
