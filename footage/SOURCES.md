# Footage sources

Videos are not committed (large files). Get them with `python tools/fetch_data.py footage`
(add `footage-large` for the 4K Perseverance file and the Apollo 11 film). The full list of
footage and datasets, with ids, credits and what each is used for, is in `data/CATALOG.md`.

| File | Source | Credit |
|---|---|---|
| `blue_ghost_m1_landing_scalpss.mp4` | NASA Image and Video Library, `Final_Out_CRF35` (2025-03-13) | NASA / Firefly Aerospace |
| `perseverance_descent_touchdown_1080p.mp4`, `perseverance_descent_touchdown.mp4` (4K) | NASA Image and Video Library, `JPL-20210222-M2020f-0001` (2021-02-22) | NASA/JPL-Caltech |
| `dart_impact_replay.mp4` | NASA Scientific Visualization Studio, item 31194 | NASA/Johns Hopkins APL |
| `apollo11_eagle_has_landed_film.mp4` | NASA Image and Video Library, `KSC-19690716-MH-NAS01-0001` (HQ-194, 1969) | NASA |

## Mission broadcasts (`broadcasts/`, via `python tools/fetch_data.py broadcasts`)

| File | Source | Credit |
|---|---|---|
| `hakuto_r_m1.mp4` | ispace "HAKUTO-R Mission 1: Landing Live Stream", YouTube `CpR1UUnix3g`, 1:07:40 to 1:11:40 | © ispace |
| `resilience.mp4` | ispace Mission 2 landing feed, re-upload on YouTube `CJzo8Dd62o4`, 1:08:00 to 1:12:10 | © ispace |
| `odysseus_im1.mp4` | "Intuitive Machines-1 Lunar Landing (Official NASA Broadcast)", YouTube `Dg2ffigGcYM`, 1:25:00 to 1:29:00 | NASA / Intuitive Machines |
| `athena_im2.mp4` | "Intuitive Machines-2 Lunar Landing (Official NASA Broadcast)", YouTube `VOPL8nhmQU4`, 0:59:20 to 1:03:20 | NASA / Intuitive Machines |

The ispace clips are ispace's property: fine to show with credit in a student demo, not to
redistribute. No descent-camera video exists for any of these four missions; the broadcasts show
mission control and a telemetry-driven animation.
