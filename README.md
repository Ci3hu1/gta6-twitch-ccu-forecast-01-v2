# GTA VI launch-day Twitch viewers forecast — v2

Entry for the make.fun bounty
[gta6-twitch-ccu-forecast-01](https://make.fun/competitions/gta6-twitch-ccu-forecast-01)
("Forecast GTA VI's launch-day Twitch viewers hour by hour", $250 USDC,
20 paid places). Built in a fresh session after the bounty opened.

## What it does

`bot.py` reads one case (`/input/<id>.in`) and writes `/output/<id>.out`:
for hours 2–24 of the release day, five quantiles (5/25/50/75/95%) of
that hour's Twitch concurrent viewers. Pure Python standard library, no
network, deterministic, ~0.02 s per case.

## The model (v2)

Per hour, regress the log-ratio of that hour's viewers to the hour-1
print on the log of the hour-1 print — fitted twice and blended:

- **Full set** (v1's calibration set, 19 launches): log-ratio OLS.
- **Rolling set** (8 launches with a rolling midnight-local unlock, the
  same unlock shape as GTA VI and as all four practice launches).

Median = `0.8 * rolling + 0.2 * full`; quantiles = median + empirical
quantiles of the pooled residuals from both fits. See `STRATEGY.md` for
the measured edge, the comparable filters, and everything tried and
dropped.

## Measured edge (practice cases, SullyGnome.com answers)

| case | v2 | v1 | flat baseline |
|------|------|------|---------------|
| p00 Wolverine | 0.1890 | 0.2475 | 0.7437 |
| p01 RDR2 | 0.1301 | 0.1676 | 0.2868 |
| p02 GoW Ragnarök | 0.1189 | 0.1172 | 0.2146 |
| p03 Spider-Man 2 | 0.2089 | 0.1858 | 0.3033 |
| **pooled** | **0.1617** | **0.1795** | **0.3871** |

90% coverage ~91% (v1: 85%). Final-like check (42 comparables):
pooled 0.1577 (v1: 0.1767).

## Files

- `bot.py` — the forecaster (packed into `main.py` by the kit).
- `main.py` — kit-packed entrypoint (generated, do not edit by hand).
- `replay.py` — local validation against the four practice cases.
- `tests/` — unit tests (`python3 tests/test_bot.py`, 6/6 pass) and the
  practice answers.
- `STRATEGY.md` — the full strategy note (measured edge, entry/exit
  rules, tried-and-dropped).
- `NOTES.md` — build, check, submit and live-score notes.

## Run locally

```sh
python3 replay.py            # practice validation
python3 tests/test_bot.py    # unit tests
```

## License

MIT — see `LICENSE`.
