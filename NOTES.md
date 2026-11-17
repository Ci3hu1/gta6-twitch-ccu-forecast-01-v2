# gta6-twitch-ccu-forecast-01-v2 — NOTES

Bounty: "Forecast GTA VI's launch-day Twitch viewers hour by hour", $250 USDC, 20 paid places (1st $50). FREE, no prerequisites. Opened 17 Nov 2026 06:00 UTC, entries close 19 Nov 2026 01:00 UTC (08:00 WIB). Final race scored live hour by hour 19 Nov 01:00 UTC – 20 Nov 00:00 UTC.

## v1 recap (for the comparison)
- Repo: https://github.com/Ci3hu1/gta6-twitch-ccu-forecast-01, commit 4180f4102a995fdd12949ae3fb233aa2068ba265. Submitted 17 Nov ~15:33 WIB on Joni's 'Setuju' (submission 01a1e8a3-8d28-72e3-a909-2b7f8071d8c8).
- Live dev score (17 Nov ~15:54 WIB): rank 245/1,311, pinball loss 0.180, typical miss 30.52%, coverage_90 0.848. Leader (0xanaksoleh, "Comparables-weighted log-curve forecast"): loss 0.122. Local pooled 0.1795 matched live 0.180 almost exactly.
- v1 model: per-hour OLS of log-ratio on log hour-1 over 19 comparables, empirical residual quantiles.

## v2 (built 17 Nov ~16:00 WIB, fresh subagent session after opening)
- Repo: https://github.com/Ci3hu1/gta6-twitch-ccu-forecast-01-v2 (public, created after opening)
- HEAD commit: f4c6af9dc7ae06398e07be03e75e21ac991d85c3 (pushed; 2 commits: 6d61291 build, f4c6af9 pack entrypoint)
- Entrypoint: main.py 5,077 bytes (makefun compress of bot.py 13,796 bytes, sha256 fbcce47fe3d26b4b85fe1f5ab21ea2e24d6b959fde599af29823337ef4f5955d; main.py sha256 be7bc39fa9996cebfd621dd605eb9bf2ecfd6192edbf9e751b90a85c6f6c5b6e)
- Model: per-hour log-ratio OLS fitted TWICE and blended — 0.8 × rolling-midnight-only fit (8 launches, unlock text says "rolling"/"midnight local") + 0.2 × full-set fit (19 launches, v1's set); quantiles = median + empirical quantiles of the POOLED residuals from both fits. Pure stdlib Python 3.12, deterministic, ~0.02 s per case.
- Kit: ~/workspace/tools/makefun/gta6-twitch-ccu-forecast-01-kit/ (skill guide 1.5.199, same kit as v1)
- Bundle: (to fill — transcripts of this session only, --muse-usage; usage row is attached by the top-level agent after this subagent finishes, as in v1)

## Kit check (to fill)
- (to fill after `node cli/makefun.mjs check`)

## Local validation (pinball loss, log scale — model vs v1 vs flat house baseline)
- p00 Marvel's Wolverine: 0.1890 vs 0.2475 vs 0.7437
- p01 Red Dead Redemption 2: 0.1301 vs 0.1676 vs 0.2868
- p02 God of War Ragnarök: 0.1189 vs 0.1172 vs 0.2146
- p03 Marvel's Spider-Man 2: 0.2089 vs 0.1858 vs 0.3033
- Pooled: 0.1617 vs 0.1795 vs 0.3871 — 9.9% better than v1, 58.2% better than baseline. 90% coverage 91% (v1: 85%).
- Final-like check (all 4 practice cases + 4 practice launches as comparables, 42 total): pooled 0.1577 vs v1 0.1767; coverage 94%.
- 6/6 tests pass; deterministic (byte-identical reruns).
- NOTE: local practice scores only. v1's local pooled matched its live dev score almost exactly (0.1795 vs 0.180), so the local numbers are a reliable proxy. Leader is at 0.122 — v2 closes about a third of v1's gap to the leader; the rest is mostly p03's idiosyncratic midday dip, which no comparable predicts.

## Submit status
- NOT SUBMITTED. Presented to Joni for a fresh 'Setuju' — do NOT submit without it. v1 remains the counted entry until/unless v2 is submitted (Force_Last: the newest entry counts).
