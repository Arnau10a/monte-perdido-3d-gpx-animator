# 🏔️ 3D GPX Route Video & Terrain Elevation Animator (Monte Perdido)

> Automated Python pipeline to convert GPS tracks (`.gpx`) into cinematic 3D relief animations, flyover videos, and dynamic Google Earth tours (`.kml`).

![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Geo](https://img.shields.io/badge/domain-GIS_%7C_3D_Relief-orange.svg)

---

## 📖 Overview

This project renders 3D flyovers of mountain expeditions (featuring the multi-day ascent to **Monte Perdido, 3,355 m** via Valle de Ordesa, Senda de los Cazadores, Refugio de Góriz and Cola de Caballo).

It fetches real Digital Elevation Model (DEM) and satellite/topographic tiles from map servers, computes real-time hillshading and lighting angles, overlays GPS telemetry from `.gpx` files, and generates smooth cinematic camera paths in full 1080p / 2K resolution.

---

## 🌟 Key Features

- **🗺️ Automated DEM & Satellite Fetching**: Downloads, stitches, and locally caches elevation tiles based on the bounding box of your route.
- **☀️ Dynamic Hillshading**: Utilizes Matplotlib's `LightSource` and 3D surface interpolation for photorealistic mountain topography and shadows.
- **🎥 Cinematic Camera Tracking**: Smooth camera spline movement that tracks elevation changes, curves, and speed profiles along the hike.
- **⚡ GPU & CPU Acceleration Modes**:
  - `main.py`: Pure CPU / Matplotlib + MoviePy pipeline.
  - `main_gpu.py`: Accelerated pipeline for high-resolution 2K/60fps rendering.
- **🌍 Google Earth Aesthetic Tour Generator**:
  - `generate_aesthetic_kml.py`: Exports optimized cinematic flight paths and waypoints directly into `.kml` format for Google Earth Desktop and Web.
  - `convert_gpx_to_kml.py`: Utility to batch-convert raw tracks into styled overlays.

---

## 📁 Repository Structure

```text
├── Dia_1_..._Goriz_Senda_de_los_cazadores_.gpx   # Day 1 GPX track
├── Dia_2_..._Goriz_Monte_Perdido_3355m_...gpx    # Day 2 GPX track (Summit)
├── Dia_2_..._Goriz_Cola_de_Caballo_...gpx       # Day 2 Descent GPX track
├── main.py                                      # Main 3D relief video generator
├── main_gpu.py                                  # High-resolution GPU rendering pipeline
├── generate_aesthetic_kml.py                    # Google Earth aesthetic tour builder
├── convert_gpx_to_kml.py                        # GPX to styled KML converter
├── requirements.txt                             # Python dependencies
└── README.md
```

---

## 🚀 Quick Start

### 1. Installation

Ensure you have Python 3.10+ installed:

```bash
# Clone the repository
git clone https://github.com/Arnau10a/monte-perdido-3d-gpx-animator.git
cd monte-perdido-3d-gpx-animator

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate 3D Video Animation

Run the generator to produce the flyover video:

```bash
python main.py
```

*The generated `.mp4` file will be saved in the root folder (cached tiles are stored in `.tile_cache`).*

### 3. Generate Google Earth KML Tour

```bash
python generate_aesthetic_kml.py
```

Double click the resulting `Monte_Perdido_Tour_Desktop.kml` to launch and play the tour in **Google Earth Pro**.

---

## 🛠️ Tech Stack

- **Python 3**
- **gpxpy** — GPS exchange format parsing
- **NumPy & SciPy** — Elevation mesh calculation and spline interpolation
- **Matplotlib (mplot3d)** — 3D terrain rendering and lighting simulation
- **MoviePy & Pillow** — Video encoding and image frame manipulation

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
