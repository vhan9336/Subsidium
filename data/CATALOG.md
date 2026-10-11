# Open footage and datasets

`python tools/fetch_data.py --list` shows what is on disk; `python tools/fetch_data.py <id or group>`
downloads it. Files land in `footage/` and `data/` (git-ignored). NASA media and data are generally
free to use with credit; other owners are named where they apply. Checked 2026-10-10.

## From the four actual crashes (used in the mission replays)

| What | Used for | Credit |
|---|---|---|
| NASA LRO narrow-angle camera images of where each lander really came down: HAKUTO-R M1 impact site (M1437131607R, 47.58°N 44.09°E), Resilience impact site (M1504323448, 60.44°N 355.41°E), Odysseus on the surface (M1463440322L, 80.13°S 1.44°E), Athena in its crater (M1496181900). `python tools/fetch_data.py sites`; cleaned copies are committed in `scenarios/sites/` | Each replay's camera descends over the real image of that mission's site, and the 3D ground uses it too. NASA's arrow and box annotations are painted out so the camera tracks terrain. Scale is not preserved: about 1 km of Moon stands in for the 0.7 m rig floor | NASA/GSFC/Arizona State University (LROC posts 1302, 1456, 1360, 1409) |
| The landing minutes of each mission's own broadcast, 4 minutes each, in `footage/broadcasts/`. `python tools/fetch_data.py broadcasts` | Plays as the large view during that mission's replay, with both brains' live verdicts drawn over it | HAKUTO-R M1 and Resilience: © ispace (Resilience via a third-party re-upload of ispace's feed). Odysseus and Athena: NASA official broadcasts with Intuitive Machines |

What these are not: none of the four broadcasts contains descent-camera video. They show mission control
and a telemetry-driven animation. The sensor readings in each replay are still this project's scaled
reconstruction of the published failure, not the mission's telemetry.

## In the project (downloaded and used)

| id | What | Used for | Credit |
|---|---|---|---|
| `blue_ghost` | Firefly Blue Ghost Mission 1 landing, 2 Mar 2025, four NASA SCALPSS cameras under the lander, with altitude printed on every frame (NASA library id `Final_Out_CRF35`) | Dashboard clip with a real altitude record; `eval/truth/blue_ghost_m1_callouts.csv` was read off those labels | NASA / Firefly Aerospace |
| `perseverance` | Perseverance descent and touchdown, onboard cameras, 18 Feb 2021 (`JPL-20210222-M2020f-0001`) | Dashboard clip, tracking only (no altitude record published with it) | NASA/JPL-Caltech |
| `dart` | DART's DRACO camera flying into Dimorphos, 26 Sep 2022 (NASA SVS 31194) | Dashboard clip, tracking only (the replay is an uneven time-lapse) | NASA/Johns Hopkins APL |
| `apollo11` | "Eagle Has Landed: The Flight of Apollo 11", NASA film HQ-194, 1969 | Slides and context; not run through the camera code (no longer fetched by tools/fetch_data.py) | NASA |
| `lro_color_8k` | LRO camera global colour mosaic from NASA's CGI Moon Kit (SVS 4720) | Ground texture in the 3D view and `--texture data/lro_texture.png` for the simulator. A 35 degree square of the southern highlands, so it is real imagery but not to lander scale | NASA's Scientific Visualization Studio |
| `lola_elevation` | LRO laser altimeter (LOLA) global elevation, same kit | Not wired into anything yet (no longer fetched by tools/fetch_data.py) | NASA's Scientific Visualization Studio |

## Found, not downloaded

Worth knowing about; each needs its own work before it is useful here.

| What | Where | Why it matters / why it was left |
|---|---|---|
| Perseverance raw descent frames: 8,496 full-resolution images from the rover down-look camera | `https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&search=%7CEDL_RDCAM` | The same descent without NASA's editing or overlays. Several GB, and the frames need ordering by spacecraft clock |
| Curiosity MARDI descent imager, images and video | NASA PDS; indexed on data.nasa.gov as "MSL MARS DESCENT IMAGER 2 EDR VIDEO V1.0" | A second straight-down Mars descent. PDS formats, no ready-made mp4 |
| MER-1/MER-2 inertial data during entry, descent and landing | NASA PDS; data.nasa.gov "MER1/MER2 MARS IMU ENTRY DESCENT AND LANDING DATA V1.0" | A real IMU record of a landing, the witness this project stands in for with a stepper |
| Ranger 9 impact film and the Ranger photograph sets (1964-65) | `https://science.nasa.gov/resource/ranger-9-impact` and `https://www.lpi.usra.edu/resources/ranger/` | A camera flying into the Moon at constant speed with a known impact time: the cleanest possible time-to-contact test. Not fetched yet |
| OSIRIS-REx touching asteroid Bennu | NASA library id `GSFC_20201021_M13745_TAG` | Slow, straight-in descent footage |
| Ingenuity Mars helicopter flight video | NASA library id `JPL-20220527-M2020f-0001-NASAs_Ingenuity_Mars_Helicopter_Captures_Video_of_Record_Flight2` | Downward navigation-camera footage including a landing |
| Blue Ghost landing broadcast and NASA's final mission update | NASA library ids `jsc2025m000008_...` and `jsc2025m000437_...` | Context for the Blue Ghost clip |
| IM-1 and IM-2 NASA news conferences | NASA library ids `jsc2023m000221-...` and `jsc2025m000013_...` | Where the Odysseus and Athena causes were explained on the record |
| LRO LOLA gridded and raw altimetry | NASA PDS; data.nasa.gov "LRO MOON LASER ALTIMETER 4 GDR V1.0" and siblings | Full-resolution lunar elevation. Very large |
| LROC narrow-angle camera terrain models, 2-5 m per pixel | `https://lroc.im-ldi.com/data` | Terrain at close to lander scale for chosen sites |
| Lunar crater database, about 1.3 million craters (Robbins 2018) | USGS Astrogeology, `astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins` | Crater statistics for a hazard argument. The download server did not answer when tried |
| POLAR stereo dataset: lunar-pole lighting recreated in a NASA Ames lab | `https://ti.arc.nasa.gov/dataset/IRG_PolarDB/` | Low sun and long shadows, the Athena failure condition. Link came from a search and was not opened |
| Boulder data, Apollo 17 Station 6 | data.nasa.gov "Preliminary Data on Boulders at Station 6 Apollo 17 Landing Site" | Real boulder sizes |
| Apollo Lunar Module 3D model | data.nasa.gov "NASA 3D Models: Apollo Lunar Module" | Could replace the hand-built lander in the 3D view |
| Lunar Orbiter photo gallery, Lunar Map Catalog, Consolidated Lunar Atlas | data.nasa.gov records pointing to LPI | Historic lunar imagery and maps |
| Blue Origin landing-sensor flight demo (BODDL-TP) and DDL-F1 | data.nasa.gov records | Project descriptions only, not sensor logs |
| Synthetic Lunar Terrain (not NASA) | Zenodo record 13218780 | Lab-built crater field with image sequences and point clouds |
| Artificial Lunar Landscape (not NASA) | Kaggle | About 10,000 rendered lunar scenes with rock labels. Needs a Kaggle account |

## Not available anywhere

No public descent-camera video or raw sensor telemetry exists for HAKUTO-R Mission 1, Resilience,
Odysseus (IM-1) or Athena (IM-2). The altitude and speed dials in the ispace broadcasts are the
closest thing; they have not been transcribed.
