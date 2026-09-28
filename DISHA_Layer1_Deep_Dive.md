# 🟢 DISHA — Layer 1: The Proactive Layer — Hyper-Detailed Technical Breakdown

> **This is the core of DISHA. Layer 1 directly and completely answers SIH26191.**  
> The pipeline: **IDENTIFY → ASSESS → PRIORITIZE → RELOCATE**

---

## 1. The Main Dashboard — `index.html` (Common Operating Picture)

`index.html` is the primary, unified command-and-control surface for SDMA/DDMA/NDRF operators. It is **not** a simple map viewer — it is an active decision environment that combines live telemetry, AI scoring, and human override into one screen.

> **`cop.html` is a separate, advanced deep-dive tab.** When an operator clicks a specific habitation on `index.html`, they can open `cop.html` to get a hyper-detailed analysis of that **single location only** — including its stress test panel, full SHAP breakdown, relocation plan, and multi-site routing comparison. Think of `index.html` as the national situation map and `cop.html` as the analyst's workbench for one specific at-risk zone.

### What the map shows simultaneously:
- 🔴 **Red / Orange / Yellow Habitation markers** — each one scored live by the XGBoost proactive models
- 🟩 **Green Safe Zones** — with live carrying capacity and current assignment status overlaid
- 🌊 **Flood Inundation Overlay** — computed from DEM simulation, cross-referenced against actual road networks
- 🚦 **Evacuation Routes** — color-coded green (safe paved) and brown (Kacha Way unpaved detour)
- 📡 **Preposition Staging Points** — computed resource stockpile locations for high-risk habitations (6–12 hr lead)
- 💨 **Wind / Weather Layer** — surface wind currents and live IMD rainfall, overlaid dynamically

### `index.html` — Clicking a Habitation → SDE (Situation Detail Engine) Panel
When an operator clicks any habitation on the main dashboard, the SDE panel opens immediately on the right side and shows:

#### A. Habitation Metadata
- **Name, ID, coordinates** (lat/lng)
- **Population** (total), **Households**, **SC/ST %**, **Women %**, **Children %**, **Elderly %**
  > This breaks down who is most vulnerable, not just a headcount.

#### B. Live Composite Risk Score
- **Flood Score** (0.0–1.0) — from XGBoost flood model
- **Landslide Score** (0.0–1.0) — from XGBoost landslide model
- **Zone Class** → RED ≥ 0.70 | ORANGE ≥ 0.45 | YELLOW ≥ 0.25 | GREEN < 0.25
- **Combined Score** = max(flood, landslide) — conservative worst-case wins
- **SHAP Explanation** — human-readable: *"Risk is HIGH primarily due to 380m from river and TWI=11.2 (terrain wetness)."*

#### C. Live Weather Trigger (Layer B Dynamic Signal)
- **Current Rain (mm/hr)** from OpenWeatherMap / IMD
- **24hr Forecast Precipitation**
- **Risk Multiplier** — if rain >50mm/day AND slope >15°, the system triggers a **Cascading Hazard Warning** and multiplies the landslide score up to 1.5x  
  > *"Extreme rainfall (63mm) is causing rapid soil saturation, amplifying baseline slope instability by 1.5x"*

#### D. CWC River Gauge (Brahmaputra — Station 028-MDG)
- **Current Water Level (m)**  
- **Warning Level**: 48.68m | **Danger Level**: 49.68m | **Highest Flood Level**: 51.46m
- **Trend**: RISING / STEADY / FALLING
- **Source**: Central Water Commission, Ministry of Jal Shakti — live scraper caches this every 15 mins

#### E. NWDP Reservoir Monitoring
- **National Water Data Portal (nwdp.nwic.gov.in)** integration
- Monitors critical upstream reservoirs: Umiam Lake (Meghalaya), Doyang Dam (Nagaland), Ranganadi Dam (Arunachal Pradesh) — all directly affect downstream Assam flood risk
- Status: **WARNING_RELEASE_IMMINENT** (>95% full), **HIGH** (>85%), **NORMAL**
  > If Ranganadi is at 99% and releasing, downstream habitations need to be warned NOW — not after the gauges spike.

#### F. Relocation Plan
- **Recommended Safe Zone** — name, distance (km), access mode
- **Route Status** — CLEAR / PARTIALLY_BLOCKED / KACHA_WAY / ISOLATED
- **Overflow Sites** — if primary zone is at capacity, the optimizer auto-assigns to overflow
- **Rejected Sites Log** — exactly WHY each safe zone was rejected (capacity, hazard exposure, inaccessibility)
- **Host Community Options** — nearby habitations that can temporarily absorb displaced population, population split proportionally

#### G. Resource Pre-Positioning (Sphere Standards)
Auto-computed per-habitation using the Sphere humanitarian standard. *(Note: This table is not displayed in the raw COP UI to save screen space; instead, the backend automatically injects it into the **Exportable PDF Evacuation Mandate** and the **Field Ops UI** `field_ops.html` for logistics teams).*
| Resource | Rate |
|---|---|
| Dewatering Pump | 1 per 1,000 people |
| Evacuation Bus | 2 per 1,000 people |
| Medical Kit | 3 per 1,000 people |
| Relief Pack (7-day) | 1 per 500 people |
| Life Jacket | 5 per 1,000 people |

> **⚙️ Configurable via Settings:** The exact mathematical rates for these Sphere resources can be adjusted live by clicking the **Gear Icon** in `index.html` (which opens the Settings Modal via `settings.js`). If a commander needs 2 buses per 500 instead of 1000, they just change the slider and the entire pipeline re-calculates instantly.

#### H. Last-Mile Dissemination Package (Sachet Assist)
- From both `index.html` (quick dispatch) and `cop.html` (full advisory screen)
- **SACHET** (MHA Emergency Alert System) — one-click push
- **SMS** (≤160 chars, auto-formatted): *"DISHA ALERT [CRITICAL]: Biswanath Forest Colony (430 residents) at HIGH flood risk. Evacuate to Nagaon Camp (8.2km). Route: CLEAR. -ASDMA"*
- **WhatsApp** (formatted with bold and emojis)
- **IVR Script** (Hindi voice alert): *"Yeh ASDMA ka flood warning hai. Biswanath mein baadh ka khatara hai..."*
- **Lead Time** — computed dynamically: `lead_time_hrs = max(6, (1.0 − combined_score) × 72)`

---

## 2. The Three XGBoost Proactive Models

All three models are `joblib`-serialized XGBoost classifiers, loaded once at server startup as a singleton (`ProactiveEngine`). They serve sub-50ms tabular inference without GPU.

### Model 1: Flood XGBoost — Assam + Kerala variants
**Training Data:**
- **HydroRIVERS flood extents** — 10,000 NE India flood events as positive samples
- **NASA SRTM DEM** — Elevation, Slope, Aspect, TRI (Terrain Ruggedness Index)
- **CHIRPS rainfall** — Annual + daily precipitation as feature inputs
- **ESA WorldCover 2021** — Vegetation proxy (bare ground = higher runoff)

**Features used for inference:**
| Feature | Description |
|---|---|
| `elevation` | Metres above sea level (SRTM) |
| `slope_deg` | Degrees of terrain slope |
| `aspect_deg` | Direction slope faces (N/S/E/W) |
| `tri` | Terrain Ruggedness Index |
| `twi` | Topographic Wetness Index — measures drainage accumulation |
| `dist_to_river_m` | Haversine distance to nearest HydroRIVERS stream |
| `precip_annual_mm` | Annual CHIRPS rainfall |
| `precip_daily_mm` | Day-of forecast rainfall (from live IMD/OWM feed) |
| `vegetation_proxy` | ESA WorldCover class score (0=urban, 1=forest) |
| `hand_proxy_m` | Height Above Nearest Drainage — key inundation indicator |

**Output:** `flood_score` (0.0–1.0 probability). SHAP TreeExplainer generates a per-sample explanation per the **Lv et al. 2022** XAI methodology.

**Cascading Hazard Logic:**  
If `precip_daily_mm > 50` AND `slope > 15°`, the flood score feeds back into the landslide model with a configurable multiplier (`cascading_multiplier` from `settings.py`).

---

### Model 2: Landslide XGBoost — Assam + Kerala variants
**Training Data:**
- **NASA Global Landslide Catalog** — 442 confirmed NE India landslide events
- Same SRTM, CHIRPS, and WorldCover feature sources as flood model

**Key distinguishing features:**
- `slope_deg` — primary driver (high slope = high susceptibility)
- `vegetation_proxy` — deforestation = root cohesion loss = higher slides
- `dist_to_river_m` — river undercutting at base = slope failure risk
- `forest_loss_pct_3yr` — **Layer 2 Strategic Feedback Injection**: if upstream deforestation > 15% over 3 years (detected by GEE satellite), landslide score is automatically amplified by 20%. This is the cross-layer feedback loop.

---

### Model 3: Heavy Rain / Cloudburst Detection XGBoost (Layer 0, shown in COP)
While technically Layer 0, its output is surfaced directly on the COP dashboard to give context for Layer 1 risk scores:
- **Features**: Humidity, dew point depression, lapse rate, atmospheric instability indices
- **Output**: Cloudburst probability, severity tier, forecasted hourly rainfall
- **Shown in:** Weather panel of cop.html, and fed into the Layer 1 `precip_daily_mm` feature

---

## 3. The Relocation Optimizer

**UI Location:** Evaluated continuously and the output is shown directly on **`index.html`** in the right-side Situation Detail Engine (SDE) panel when a habitation is clicked (under Routing Status & Assigned Relief Camp).
**Algorithm:** `scipy.optimize.linear_sum_assignment` (Hungarian algorithm for bipartite matching — optimal cost minimization).

### How it works:
1. All at-risk habitations are **scored and tiered** by the proactive engine:
   - **Immediate** (score ≥ 0.70) — move NOW
   - **Short-term** (0.40–0.70) — move within 24hrs
   - **Medium-term** (< 0.40) — monitor and prepare
2. All candidate safe zones have a **hard capacity constraint**: `capacity_total = site_area_sqm × 3.5 persons/m²` (Sphere humanitarian standard).
3. The optimizer solves the assignment problem: minimize total harm (a function of distance × vulnerability score) subject to each site's hard capacity limit.
4. If a site is full, the optimizer auto-cascades overflow population to the next-best site.
5. Any habitation that cannot be assigned (all sites full or inaccessible) is flagged as **UNASSIGNED** — shown as a critical alert on the COP.

---

## 4. Hazard-Aware Routing Engine

**UI Location:** Visible as the route lines on `index.html` and `cop.html`.  
This is the most technically sophisticated routing system in DISHA.

### Step-by-Step:
1. **Primary: Pre-cached GraphML** — A full OSMnx road graph of Guwahati is pre-loaded at server startup from `guwahati_drive.graphml` to avoid Overpass API timeouts entirely. **0ms graph load time.**
2. **Flood pruning:** Every road edge in the graph is checked against the active flood inundation polygon using **Shapely** intersection. Flooded edges are permanently removed from the working graph before pathfinding begins.
3. **Pathfinding on pruned graph:** `networkx.shortest_path(G_pruned, weight='length')` finds the shortest physically safe route.
4. **Kacha Way generation:** If the habitation's exact coordinates are off-road (distance from nearest road node > 0.0001 degrees ≈ 10m), a brown **unpaved dirt track (Kacha Way)** is generated from the habitation to the nearest safe road node. If even this straight-line Kacha Way crosses flood water, a geometric detour is calculated by pushing the midpoint away from the flood centroid by ~500m.
5. **ISOLATED handling:** If no path exists on the pruned graph, the system returns `route_status: ISOLATED` and the UI escalates to boat/helicopter recommendation.
6. **OSRM Fallback:** If the GraphML is missing or the graph query fails for any reason, the system falls back to the **OSRM Public Routing API** (`router.project-osrm.org`) which provides real curvy road geometry in <1 second. Results are cached to `route_cache.json` for zero-latency replay.

---

## 5. What-If Stress Tester

**UI Location:** Located exclusively in the **`cop.html`** advanced analysis dashboard.  
This is **Innovation 4** — an Incident Commander can inject failure scenarios BEFORE deployment and see exactly how the relocation plan degrades.

### Available Scenarios (pre-built templates):
| ID | Label | What it tests |
|---|---|---|
| `bridge_blocked` | 🌉 NH-37 Bridge Blocked | Forces optimizer to find alternate routes |
| `shelter_30pct` | 🏫 Primary Shelter -30% | Nagaon Stadium partially damaged |
| `bus_fleet_50pct` | 🚌 Bus Fleet -50% | Evacuation waves doubled, hrs delay computed |
| `extreme_rain` | 🌧️ Rainfall Spike +90% | Flood zones expand, more habitations enter RED |
| `cascade` | 🔴 Cascade Failure | All three above simultaneously — worst case |

### Output:
- **Before plan** (current live state)  
- **After plan** (stressed state)  
- **Delta** — how many more habitations become UNASSIGNED, how many evacuation waves are added, how many hours delay
- **Severity label**: RESILIENT / MODERATE / HIGH / CRITICAL

The Stress Test runs the full optimizer on a **deep-copied** set of inputs — it never mutates live state, so it is completely safe to run during an active operation.

---

## 6. 3D Simulation & 36-Hour Lead Time

**UI Location:** `dashboard/simulation.html` + `js/simulation_3d.js` (Accessible via "View 3D Simulation" in `cop.html`)  
A 3D terrain visualization that shows how flood water will physically propagate over the actual DEM terrain over a **T+36 hour window**.

### How the T+36 hour window is used:
The system models a continuous 36-hour predictive timeframe (T+0 to T+36). 
Instead of a static map, the simulation dynamically projects the incoming hazard over this exact 36-hour horizon based on live precipitation forecasts and terrain choke points.

### What the 3D simulation visualizes:
- Real terrain elevation mesh from DEM data
- Time-stepped flood wave propagation (frame-by-frame across 36hr)
- Which habitations get inundated at which hour
- Which roads get cut off and at what time
- Dynamic camera that auto-focuses on the highest-risk zone

---

## 7. Field Ops & SAR App

### Web: `dashboard/field_ops.html`
- Responder-facing interface with simplified HazardMap
- Shows assigned route for each team in real time
- Allows responders to mark a habitation as EVACUATED, PARTIALLY_EVACUATED, or INACCESSIBLE
- Ground reports feed back into the COP, which can trigger the optimizer to re-run

### Mobile: `sar_app/` (Flutter)
- Offline-capable mobile app for field responders with no internet
- **`field_report_screen.dart`** — allows NDRF/SDRF teams to log:
  - GPS location (auto-captured)
  - Habitation status (safe / flooded / evacuated)
  - Casualty/displacement count
  - Photographic evidence
- Reports are queued locally and synced when connectivity is restored via `POST /field-reports/`
- Triggers **hazard polygon creation** on the server: field-confirmed flood zones are added to `relocation_state.py`'s hazard polygon registry, which the next optimizer run will treat as hard blockages

---

## Summary: Layer 1 API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /advisory/{hab_id}` | Full relocation advisory for one habitation |
| `GET /advisory/safe-zones` | All safe zones with live capacity |
| `GET /advisory/pre-position/{region}` | Resource pre-staging intel for high-risk habs |
| `POST /route/` | Compute hazard-aware evacuation route |
| `POST /route/reachable` | Find first reachable safe zone across candidates |
| `GET /cwc/guwahati` | Live Brahmaputra river gauge (CWC Station 028-MDG) |
| `GET /nwdp/reservoirs` | Upstream dam levels (Umiam, Doyang, Ranganadi) |
| `POST /relocation/plan` | Run the full bipartite assignment optimizer |
| `POST /stress-test/inject` | What-If scenario injection (no live state mutation) |
| `GET /stress-test/scenarios` | Pre-built stress scenario templates |
| `POST /field-reports/` | Submit ground-truth report from SAR mobile app |
| `GET /live-risk/{region}` | Live composite risk scores for all habitations |
