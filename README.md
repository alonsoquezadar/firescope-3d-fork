# FireScope 3D

> 🌐 **Demo:** https://alonsoquezadar.github.io/firescope-3d-fork/ — runs entirely in your browser: no server, no keys.
>
> 📘 Pitch y explicación completa (ES): [docs/PITCH_Y_FUNCIONAMIENTO.md](docs/PITCH_Y_FUNCIONAMIENTO.md) · 🗺️ Plan de mejora: [docs/PLAN_DE_MEJORA.md](docs/PLAN_DE_MEJORA.md)

**We turn wildfire drone footage into a time-aware 3D operational picture.**

Built by [Alonso](https://github.com/alonsoquezadar) and [Ali](https://github.com/aleetreny) for the **VAST Builders Challenge hackathon on 17 October 2026**.

FireScope 3D takes drone video of a fire, measures what the camera sees (burned ground, flames, smoke), projects it onto real terrain, and lets you scrub through time, click an event to see the exact video evidence, search the footage and ask questions about the incident in English or Spanish.

The interface recreates the "FireTrace" wildfire forensic prototype (Dilum Sanjaya / Claude, shared by Anthropic). Its layout is a full-bleed 3D terrain with a right-hand layers and incident panel, a bottom timeline with linked charts and a key-events column, Incident / Drones / Resources modes, a drone camera window, and 2D/3D map switching. Here it runs on **real data**.

> Exploratory decision-support prototype. **Not** a certified emergency-management or fire-spread prediction system.

---

## What you are looking at

| | Source | Status |
|---|---|---|
| Drone footage | **BurnedAreaUAV v1.1** (Zenodo 7944963, CC-BY-4.0): 15 min of RGB video of a prescribed burn at Torre do Pinhão, Portugal, from a hovering DJI Phantom 4 Pro | Real, replayed as **DRONE REPLAY**, never labelled live |
| Camera pose | DJI XMP metadata of the dataset's photos (GPS, 24.9 m AGL, gimbal yaw −46.7°, pitch −28.9°, calibrated focal length) | Real |
| Terrain | AWS Terrain Tiles (Terrarium) DEM in three rings of detail out to ~70 km; Esri World Imagery drives the stylized ground and vegetation | Real elevation, stylized rendering, **1.8× vertical exaggeration (labelled)** |
| Burned area / flames | `backend/firescope/segment.py`: RGB segmentation with temporal accumulation | Model output, **evaluated against the manual masks** (below) |
| Georeferencing | Pinhole camera, rays marched onto the DEM (`geo.py`) | **Approximate** (`camera_model_dem`) |
| Events | Measured changes: area growth, flames outside the scar, smoke surges, peak flame extent | Derived, `confidence: null`, `review_required: true` |
| Rate of spread | Leading edge of the burned outline vs one minute earlier (90th percentile of the displacement, `frontend/scripts/lib/front-advance.mjs`): mean 2.8 m/min, peak 10.4 m/min | Derived, visible front only |
| Ask | Incident analyst in the browser (`frontend/src/agent/analyst.ts`): detects the intent of the question (where, when, how much, fastest growth, spot fires, smoke, weather, drone, accuracy, risk, resources…), answers from the recorded data in English or Spanish, and cites the clips it used | Derived. Rule-based, **no language model, nothing generated** |
| Search | Keyword search (EN/ES) over the recorded events and per-clip measurements (`frontend/src/agent/search.ts`) | Derived. Searches what was measured, not the pixels |
| Hotspots | Visible-flame blob centroids. **RGB cannot measure temperature**, so `temperature_c` is always `null` | Model |
| Weather card | ERA5 reanalysis via Open-Meteo for the site and hour | External (reanalysis, not on-site) |
| Drones FT-02…FT-06, Resources (13 units), drops, fire lines, large-fire scenario | Deterministic exercise around the real incident; sim drone cameras render the 3D twin | **Simulated**, tagged SIM in the UI, never a forecast |
| Trees, smoke particles | Rendered for readability | Stylized |

Every metric in the UI carries a provenance chip (`model`, `derived`, `ground_truth`, `external`, `sim`), and the **About** tab lists how each part was produced.

## Evaluation (reproducible)

`python -m firescope.pipeline` → `data/processed/drone_replay_01/eval.json`

| Metric (226 annotated frames, every 100th frame) | Value |
|---|---|
| Mean IoU, cumulative burned mask vs manual mask (image space) | **0.68** |
| Precision / recall | 0.76 / 0.85 |
| Mean IoU after projecting both onto the DEM (ground space) | **0.71** |
| Pipeline runtime, full 15 min video on an M5 Pro CPU | ~12 s |

The ground-truth masks can be toggled on the map (Layers → Ground Truth), shown in blue against the model's scar.

## Architecture

```
 OFFLINE (once per incident)                              STATIC SITE (GitHub Pages)
 ┌──────────────────────────────────────┐                ┌───────────────────────────────────────────┐
 │ backend/firescope/pipeline.py         │                │ incidents/index.json                      │
 │  video → frames every 4 s → masks     │  export-static │ incidents/<id>/manifest.json  (methods,   │
 │  (burned / flame / smoke, accumulated)│ ─────────────▶ │   attribution) · incident · sources ·     │
 │  → pinhole camera + DEM ray cast      │   (npm build)  │   timeline · events · observations ·      │
 │  → GeoJSON polygons, timeline, events │                │   weather · clips · eval · media/ (video, │
 │  → eval vs manual masks · ERA5        │                │   thumbnails)                             │
 └──────────────────────────────────────┘                └──────────────────────┬────────────────────┘
                                                                                ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ React + Three.js dashboard: DEM terrain in LOD rings · draped fire-mask shader · bloom flames ·     │
 │ smoke · drone + frustum · timeline (master clock) · charts · drone feed synced to the timeline ·    │
 │ incident analyst + search in the browser (src/agent) · simulated ops (src/sim) · presentation mode  │
 └────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Frontend** (`frontend/`): React 19, TypeScript, Vite, Three.js (custom terrain shader, draped canvas masks for burned / active / change, UnrealBloom, GPU point-sprite flames and smoke, instanced vegetation), Zustand. The timeline is the single clock: map overlays, charts, events, the drone video and the panels all follow it.
* **Data client** (`frontend/src/api/client.ts`): static mode by default (reads `incidents/<id>/`, chosen with `?incident=<id>` or the index default); optional API mode against the FastAPI backend with `VITE_API_BASE`.
* **Pipeline / optional backend** (`backend/firescope/`): `pipeline.py` (video → masks → polygons → timeline/events/eval), `geo.py` (DEM + camera), `segment.py`, `weather.py`, `app.py` (FastAPI, `docs/api-contract.md`). The hackathon's NVIDIA adapters (`nvidia.py`, `cosmos_job.py`) are still in the tree but unused by the demo.

## Run it

```bash
cd frontend && npm install
npm run dev                  # static demo on the exported incident → http://localhost:5173
npm run build                # → dist/ (what GitHub Pages serves; relative paths, works under any sub-path)
```

`npm run dev` and `npm run build` first run `scripts/export-static.mjs`, which packages `data/processed/drone_replay_01/` and `media/` into `public/incidents/`.

To recompute the data from the original dataset:

```bash
# data (≈1 GB, CC-BY-4.0): KML, photo metadata and the video/masks archive from Zenodo 7944963
mkdir -p data/raw/burnedareauav && cd data/raw/burnedareauav
for f in pinhao_cell_precribed_area.kml uav_photo_1_metadata.JPG BurnedAreaUAV_dataset_v1.rar; do curl -LO "https://zenodo.org/api/records/7944963/files/$f/content" -o $f; done
bsdtar -xf BurnedAreaUAV_dataset_v1.rar && cd ../../..
cd backend && uv venv && uv pip install -r requirements.txt
.venv/bin/python -m firescope.pipeline        # CV + georeferencing + eval (~15 s) → data/processed/
.venv/bin/uvicorn firescope.app:app --port 8000   # optional: the same UI against the API → VITE_API_BASE=http://localhost:8000 npm run dev
```

The browser video is a 960×540 H.264 copy at `media/drone_replay_01.mp4` (two-pass ~520 kb/s so it fits GitHub's 100 MB file limit):
`ffmpeg -i <original> -an -vf "scale=960:540:flags=lanczos,hqdn3d=1.5:1.5:4:4" -c:v libx264 -preset slow -b:v 520k -maxrate 900k -bufsize 1800k -g 100 -pass 1|2 -movflags +faststart media/drone_replay_01.mp4`

## Tests

```bash
cd frontend
node scripts/e2e.mjs 'http://localhost:4173/<base>/?nointro'                 # 76 checks: layout at 6 viewports + functional walk + FPS
URL='http://localhost:4173/<base>/?nointro' node scripts/present-test.mjs out   # presentation mode, all 18 chapters
node scripts/audit/states.mjs '<url>' out                                       # overlap / clipping sweep (see scripts/audit/README.md)
cd ../backend && python -m pytest -q                                            # pipeline + API tests
```

## Publish (GitHub Pages)

Every push to `main` runs [`.github/workflows/pages.yml`](.github/workflows/pages.yml): it exports the incident package, builds the dashboard with relative paths (so it works under any repository name) and deploys it to GitHub Pages. Terrain and imagery tiles stream from public tile servers in the browser.

## Limitations (honest)

* RGB only: no temperatures. Smoke can hide or mimic burned ground; the 3-frame vote and monotonic accumulation reduce but don't remove this.
* Georeferencing assumes the video pose equals the photo pose (same hover) and a flat-ish DEM near the drone. It is approximate, with an unknown RMSE. The far field (above 21% of the frame) is excluded.
* Only the drone's field of view (~100 m) is observed. The planned burn-cell outline comes from the KML and is not an observation.
* The video's wall-clock start (12:33:00Z) is an assumption anchored to the photo metadata.
* The analyst and search work on the recorded measurements and events only; they cannot answer about things that were not measured.
* The large-fire scenario, fleet and resources are an illustrative simulation.

## History

FireScope 3D was built by [Alonso](https://github.com/alonsoquezadar) and [Ali](https://github.com/aleetreny) in a day at the **VAST Builders Challenge (17 Oct 2026)**. There, clip descriptions and video search ran live on NVIDIA Cosmos Reason / Cosmos Embed1 on the event's Kubernetes cluster. That cluster is gone and those outputs were not kept, so they are not reproduced here: [docs/historia-hackathon.md](docs/historia-hackathon.md).

## Credits

BurnedAreaUAV, Ribeiro et al. 2023 (CC-BY-4.0) · AWS Terrain Tiles · Esri World Imagery · ERA5 via Open-Meteo · UI inspired by FireTrace (Dilum Sanjaya). The FireScope implementation is independent.
