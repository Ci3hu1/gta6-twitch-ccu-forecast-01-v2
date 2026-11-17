"""Unit tests for bot.py (the GTA VI Twitch-viewers forecaster).

Run:  python3 -m pytest tests/test_bot.py -q
  or: python3 tests/test_bot.py

The practice answers are SullyGnome.com's hourly Twitch category
averages for the four practice launches (the same source the kit's
cases use), fetched once from
  https://sullygnome.com/api/charts/linecharts/getconfig/GameViewers/...
for the release month of each launch; each case's hour-1 value matches
its .in file's known print exactly.
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIT_INPUT = Path.home() / "workspace/tools/makefun/gta6-twitch-ccu-forecast-01-kit/input"
sys.path.insert(0, str(REPO))

import bot  # noqa: E402

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
ANSWERS = json.loads((REPO / "tests/practice_answers.json").read_text())


def pinball(y: float, q: float, tau: float) -> float:
    d = math.log(max(y, 1.0)) - math.log(q)
    return 2 * max(tau * d, (tau - 1) * d)


def score(forecast: dict, answers: dict) -> float:
    total, n = 0.0, 0
    by_hour = {row["hour"]: row["q"] for row in forecast["hours"]}
    for hour, y in answers.items():
        if hour == 1:
            continue
        for tau, q in zip(LEVELS, by_hour[hour]):
            total += pinball(y, q, tau)
            n += 1
    return total / n


class TestBot(unittest.TestCase):
    def test_output_shape_all_practice_cases(self):
        """23 rows, hours 2..24, five finite non-decreasing quantiles."""
        for pid in ("p00", "p01", "p02", "p03"):
            case = json.loads((KIT_INPUT / f"{pid}.in").read_text())
            out = bot.forecast_case(case)
            self.assertEqual(set(out), {"hours"})
            self.assertEqual(len(out["hours"]), 23)
            self.assertEqual([r["hour"] for r in out["hours"]], list(range(2, 25)))
            for row in out["hours"]:
                self.assertEqual(set(row), {"hour", "q"})
                self.assertEqual(len(row["q"]), 5)
                for i, q in enumerate(row["q"]):
                    self.assertTrue(math.isfinite(q) and 0 < q <= 1_000_000_000, q)
                    if i:
                        self.assertGreaterEqual(q, row["q"][i - 1])

    def test_beats_flat_baseline_on_every_practice_case(self):
        """Pooled pinball loss must beat the house baseline (0.3871)."""
        pooled_model, pooled_base = 0.0, 0.0
        for pid in ("p00", "p01", "p02", "p03"):
            case = json.loads((KIT_INPUT / f"{pid}.in").read_text())
            answers = {int(h): v for h, v in ANSWERS[pid].items()}
            model = score(bot.forecast_case(case), answers)
            base = score(bot.baseline_forecast(case), answers)
            self.assertLess(model, base, f"{pid}: model {model:.4f} vs baseline {base:.4f}")
            pooled_model += model
            pooled_base += base
        self.assertLess(pooled_model / 4, 0.17)
        self.assertLess(pooled_model / 4, pooled_base / 4)

    def test_deterministic_two_runs_byte_identical(self):
        """Two runs of the program write byte-identical outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "out1"
            out2 = Path(tmp) / "out2"
            env = dict(os.environ, MAKEFUN_INPUT_DIR=str(KIT_INPUT))
            for outdir in (out1, out2):
                env["MAKEFUN_OUTPUT_DIR"] = str(outdir)
                proc = subprocess.run(
                    [sys.executable, str(REPO / "bot.py")],
                    env=env, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
            for pid in ("p00", "p01", "p02", "p03"):
                self.assertEqual(
                    (out1 / f"{pid}.out").read_bytes(),
                    (out2 / f"{pid}.out").read_bytes(),
                )

    def test_output_files_small_and_valid_json(self):
        """Each .out is valid JSON and well under the 65,536-byte cap."""
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "out"
            env = dict(os.environ, MAKEFUN_INPUT_DIR=str(KIT_INPUT),
                       MAKEFUN_OUTPUT_DIR=str(outdir))
            proc = subprocess.run(
                [sys.executable, str(REPO / "bot.py")],
                env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for pid in ("p00", "p01", "p02", "p03"):
                data = (outdir / f"{pid}.out").read_bytes()
                self.assertLess(len(data), 65536)
                json.loads(data)

    def test_fast_enough(self):
        """One case must run far inside the 8-second budget."""
        import time
        case = json.loads((KIT_INPUT / "p00.in").read_text())
        start = time.monotonic()
        bot.forecast_case(case)
        self.assertLess(time.monotonic() - start, 2.0)

    def test_fallback_never_crashes(self):
        """A case with no usable comparables still yields a valid forecast."""
        case = json.loads((KIT_INPUT / "p00.in").read_text())
        case["comparables"] = []
        out = bot.forecast_case(case)
        self.assertEqual(len(out["hours"]), 23)


if __name__ == "__main__":
    unittest.main(verbosity=2)
