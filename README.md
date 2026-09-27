# 🚨 DISHA — Dynamic Information System for Hazard Assessment

**Team:** Binary Nomads  
**Hackathon:** Smart India Hackathon (SIH) 2026  
**Problem Statement:** SIH26191 — Ministry of Home Affairs (NDRF / DM Division)  

---

## 📖 Overview

**DISHA** is an AI-driven, multi-layered decision support platform designed to answer the core challenge of SIH26191: *Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations.* 

Unlike traditional platforms that only act during a crisis, DISHA spans **long-term strategy, proactive evacuation, and post-disaster response** through a unified, 4-Layer architecture.

---

## 🏗️ The 4-Layer Architecture

DISHA is built on a highly modular 4-layer system, each operating on a different timescale and serving a specific disaster management goal.

### 🟡 Layer 0: The Reactive Layer (Hours to Days)
**Goal:** Detect hyper-local, fast-developing atmospheric threats before they manifest on the ground.
- **How it works:** Uses a Thermodynamic XGBoost model to process meteorological and sensor data, identifying rapidly developing events like **Cloudbursts**.
- **Impact:** Gives authorities critical lead time to mobilize teams before a sudden-onset disaster is visible on standard optical satellites.

### 🟢 Layer 1: The Proactive Layer (The Core SIH26191 Mandate)
**Goal:** Map immediate danger, calculate safe capacities, and optimize relocation routes.
This is the core pipeline addressing the SIH problem statement (**IDENTIFY → ASSESS → PRIORITIZE → RELOCATE**).
- **Red Zone Mapping:** ONNX-optimized **U-Net** (Flood) and **ResNet50** (Landslide) models map hazard susceptibility.
- **Relocation Engine:** AI-optimized bipartite matching assigns vulnerable populations to safe zones based on strict **Carrying Capacity** constraints.
- **Dynamic Routing:** Instantly routes convoys around flooded roads using OSMnx and an **OSRM Fallback Engine**, generating unpaved "Kacha Way" detours if a community is isolated.

### 🔵 Layer 2: The Strategic Observatory (Months to Years)
**Goal:** Long-term urban planning and vulnerability tracking to prevent habitations from entering Layer 1 danger thresholds.
- **UFRI (Urban Flood Risk Index):** A forensic 10-layer spatial intelligence model specifically for urban basins (e.g., Guwahati). It calculates live flood risk using the Rational Method (`Q = CiA`), flagging critical drainage thresholds before city-wide flooding occurs.
- **Long-term Watchlist:** Monitors slow-moving disasters like Coastal Erosion, Glacial Lake Outburst Floods (GLOF) expansion, and Urban Subsidence using Earth Engine timeseries data.

### 🔴 Layer 3: Damage Assessment & Self-Calibration (Post-Disaster)
**Goal:** Classify structural damage to buildings after a hazard event.
- **Siamese ResNet50 Model:** Compares pre- and post-disaster satellite imagery pixel-by-pixel to classify damage as *minor, moderate, or severe*.
- **Self-Calibration (Human-in-the-Loop):** Machine learning isn't perfect. SDMA operators can manually verify or correct the AI's damage predictions via the UI. This feedback is captured in the `/feedback` loop to continually retrain and self-calibrate the model, making it smarter for the next disaster.

---

## 👥 Stakeholder Views: DM vs. MHA

DISHA recognizes that a District Magistrate (DM) and the Ministry of Home Affairs (MHA) have very different informational needs.
- **DM (District Magistrate) View:** Granular, hyper-local, and highly actionable. DMs see exact evacuation routes, individual building damage, carrying capacities of local schools/camps, and real-time alerts.
- **MHA (Ministry of Home Affairs) View:** Aggregated, strategic oversight. The MHA dashboard provides state-wide vulnerability trends, macro-level resource deployment needs, and long-term Layer 2 strategic fund allocation insights.

---

## 🚀 Advanced Platform Features

### 🌍 3D Simulation & Forensic Intelligence
To truly understand urban vulnerability, DISHA includes a high-fidelity **3D Guwahati Deep-Dive** (built on WebGL/Cesium logic). It visualizes the **UFRI** spatially, allowing operators to see exactly how water will pool in urban basins, which specific wards will drown first, and where drainage infrastructure is failing geometrically.

### 👮 Field Ops & SAR App
DISHA extends beyond the command center directly to the responders. The **Field Ops** module (and the connected `sar_app` Flutter application) connects ground teams with the Common Operating Picture (COP). Responders receive hazard-aware routes and can push live ground-truth data back to the central server.

### 🤖 Integration Agent (AI Orchestrator)
A sophisticated LLM-backed **Integration Agent** bridges the gap between raw telemetry and human operators. It synthesizes CWC (Central Water Commission) river gauges, IMD weather feeds, and the outputs of the four visual layers into plain-English tactical briefings and automated WhatsApp/SMS warnings.

---

## 🧠 Explanation of AI Models

All deep learning models in DISHA run on **ONNX Runtime (CUDA Execution Provider)**, allowing parallel, zero-copy GPU inference in under 1.5 seconds.
1. **Flood Detection:** `SegFormer / U-Net`. Performs binary segmentation on optical imagery to identify standing water extents.
2. **Landslide Detection:** `ResNet50 U-Net`. Analyzes terrain and geographical visual features to identify active slope failures.
3. **Damage Classification (Layer 3):** `Siamese ResNet50`. Takes two inputs (Pre-disaster and Post-disaster imagery) to generate a 3-class damage severity mask.
4. **Thermodynamic Risk (Layer 0):** `XGBoost`. Tabular regression on atmospheric variables (humidity, temperature, pressure changes) to predict cloudburst probability.

---

## 💻 Setup & Installation

### Backend (FastAPI + ONNX)
```bash
git clone https://github.com/pawani-deshmukh1/BINARY-NOMADS-SIH26191-DISHA.git
cd BINARY-NOMADS-SIH26191-DISHA/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### Frontend (Dashboard)
```bash
cd dashboard
npx serve .
```

*Built with ❤️ by Team Binary Nomads for SIH 2026.*
