# 📦 GeoKurir Malang — Spatial Package Delivery Zone Clustering Using K-Means++ and HBCDP

<p align="center">
  <img src="https://img.shields.io/badge/Field-Machine_Learning-blue?style=for-the-badge" alt="Field">
  <img src="https://img.shields.io/badge/Method-K--Means%2B%2B_%26_HBCDP-orange?style=for-the-badge" alt="Method">
  <img src="https://img.shields.io/badge/Framework-Flask-lightgrey?style=for-the-badge&logo=flask" alt="Framework">
  <img src="https://img.shields.io/badge/Database-PostgreSQL-316192?style=for-the-badge&logo=postgresql" alt="Database">
</p>

## 🧠 Why I Built This

Last-mile parcel delivery is not only about assigning packages to couriers — in reality, **uneven parcel distributions and scattered routes create major operational bottlenecks**.

At **PT Pos Indonesia KCU Malang**, daily delivery volumes fluctuate across five districts in Kota Malang. When delivery points assigned to a courier are geographically dispersed or parcel counts become unbalanced, some couriers handle disproportionately heavy workloads while crossing overlapping areas.

This led me to a key question:

> *What if a delivery planning system could group scattered package addresses into geographically compact zones while balancing courier workloads automatically?*

---

## 🎯 Project Context

- **Type:** Undergraduate Final Thesis (*Skripsi D4*)
- **Field:** Applied Informatics Engineering / Geospatial Machine Learning
- **Role:** Researcher & Full-Stack System Developer
- **Institution:** State Polytechnic of Malang (*Politeknik Negeri Malang*)
- **Validation:** Evaluated on historical PT Pos Indonesia KCU Malang delivery records (August 2025 dataset across five districts in Kota Malang) and benchmarked against actual field courier assignments (`Petugas`)

---

## 👨‍💻 My Contribution

As the individual researcher and developer of this project, I was responsible for designing and implementing the end-to-end geospatial clustering web system, including multi-format dataset ingestion (`CSV`/`XLSX`/`XLS`), address cleaning, Google Maps geocoding integration, planar meter coordinate projection, actual PT Pos baseline evaluation (`evaluasi_aktual`), two-stage **K-Means++** and **HBCDP** clustering, cluster quality and workload evaluation, interactive map visualization, and Dockerized PostgreSQL deployment.

I also calibrated spatial constraints against Kota Malang's five subdistrict centroids and verified system reliability through automated unit and database integration tests.

---

## ⚙️ My Approach (How I Think)

Instead of applying standard unconstrained clustering directly to raw addresses, I focused on three key principles:

### 1. Spatial Proximity Over Arbitrary Assignment

Courier zones must represent contiguous, geographically logical areas rather than scattered stops.

➡️ I projected geocoded recipient coordinates into **planar meter coordinates** and calculated **Euclidean distances**, grouping nearby delivery points into cohesive zones.

---

### 2. Workload Balance Over Unconstrained Clustering

Standard K-Means minimizes distance to centroids, but it often produces severely uneven parcel counts across couriers.

➡️ I implemented a two-stage pipeline combining **K-Means++** spatial initialization with **HBCDP (Heuristic Balancing for Courier Delivery Zones)** and a calibrated maximum distance threshold ($D = 5,285.15\text{ m}$) to equalize workload without fragmenting zones.

---

### 3. Fair Baseline Benchmarking

Algorithmic metrics are only meaningful when compared fairly against real operations.

➡️ I built an automated baseline evaluation service (`evaluasi_aktual`) that benchmarks algorithmic clusters head-to-head against actual PT Pos courier assignments (`Petugas`) on the exact same geocoded parcel subset.

---

## 📌 Project Overview
An end-to-end geospatial web application built with **Flask** and **PostgreSQL** to optimize last-mile package delivery zones in Kota Malang by combining address geocoding, actual courier baseline benchmarking, two-stage spatial workload balancing (**K-Means++** + **HBCDP**), and interactive map visualization.

---

## 🚀 Key Features
- **📍 Multi-Format Upload & Google Maps Geocoding:** Processes `CSV`, `XLSX`, and `XLS` delivery records, cleans recipient addresses, validates coordinates within Kota Malang boundaries, and geocodes addresses via the Google Maps Geocoding API.
- **📊 Actual PT Pos Baseline Evaluation (`evaluasi_aktual`):** Preserves the optional **`Petugas`** column during preprocessing, computes baseline metrics right after geocoding, and displays them on the **Upload** page (before clustering starts), **Dashboard**, **Aktual PT Pos Zone** tab, and **Evaluation** page.
- **🧠 Two-Stage Spatial Clustering (K-Means++ & HBCDP):** Initializes spatially well-separated centroids using K-Means++ and iteratively rebalances parcel counts using HBCDP with stage-by-stage transition logs.
- **⚖️ Head-to-Head Evaluation in Meter Coordinates:** Computes **Silhouette Score**, **Davies-Bouldin Index (DBI)**, **workload population variance ($Z_1$)**, and **reassignment distance cost ($Z_2$)** in planar meters via `services/actual_evaluation_service.py`.
- **🗺️ Interactive Zone Mapping:** Renders delivery points, cluster centroids, Convex Hull polygon boundaries (Shapely), and actual courier territories on an interactive Google Maps interface.
- **📥 Structured Zone Export:** Exports clustered delivery assignments enriched with the **`Petugas Aktual`** column for direct operational comparison.

---

## 🧠 Design Reasoning 

### **The Problem: Uneven Courier Workloads & Dispersed Routes**
Analyzing historical parcel distribution at PT Pos Indonesia KCU Malang revealed two operational challenges:
- **Spatial Overlap:** Daily shifts in package destinations can cause courier delivery areas to stretch across distant neighborhoods.
- **Workload Imbalance:** Without systematic capacity balancing, individual couriers can receive significantly different daily parcel counts.

### **The Research: Beyond Standard K-Means**
Conventional K-Means focuses purely on minimizing spatial distance, offering no control over cluster size equality. Conversely, forcing strict equal cluster sizes without spatial boundaries can assign far-away packages to an underloaded courier.

### **The Solution: Why K-Means++ + HBCDP?**
1. **Spatially Sound Initialization (K-Means++):** Distributes initial cluster centers across Kota Malang's five districts to prevent poor local optima.
2. **Distance-Bounded Balancing (HBCDP):** Reassigns boundary parcels toward balanced cluster capacities ($\approx n / K$) while enforcing a maximum spatial distance constraint ($D = 5,285.15\text{ m}$, derived from the mean distance across Kota Malang's 5 subdistrict centroids).
3. **Strict Evaluation & Integrity Rules:**
   - **Manual $K$ vs. Actual Couriers:** Target cluster count $K$ is set manually and may differ from the actual number of couriers; K-Means++ and HBCDP always run across **all successfully geocoded points**.
   - **Fair Subset Comparison:** Head-to-head comparisons of **Silhouette Score, DBI, and $Z_1$** evaluate the exact same subset of parcels carrying a `Petugas` label using the algorithm's assigned cluster labels directly without re-clustering.
   - **Missing `Petugas` Handling:** If the uploaded file omits `Petugas`, actual baseline metrics display as `N/A` while clustering still runs on all geocoded points; **$Z_2$** and HBCDP stage histories remain full-dataset diagnostics.
   - **Normalization & Null Safety:** `Petugas` names are whitespace-trimmed while remaining case-sensitive. Undefined metrics (such as fewer than two valid clusters) are stored as `NULL` with an explicit reason rather than `0`, whereas a single courier validly produces $Z_1 = 0$.
   - **Data Fingerprinting & Timer Scope:** A data fingerprint detects changes to coordinates or `Petugas` labels so re-completing geocoding refreshes `evaluasi_aktual` (changing $K$ alone does not recompute the actual baseline). The runtime timer strictly covers **K-Means++ initialization through HBCDP completion**.

### Evaluation Metrics Summary
| Metric | Dimension | Interpretation |
| :--- | :--- | :--- |
| **Silhouette Score** | Spatial Cohesion & Separation | Ranges from `-1` to `1` (**higher is better**). |
| **Davies-Bouldin Index (DBI)** | Cluster Similarity | Measures intra-cluster dispersion vs. inter-cluster separation (**lower is better**). |
| **$Z_1$ (Workload Variance)** | Workload Balance | Population variance of parcel counts per courier/cluster (**lower is more balanced**). |
| **$Z_2$ (Reassignment Cost)** | Balancing Distance Cost | Cumulative planar meter distance incurred when shifting points during HBCDP balancing. |

---

## 🤝 Collaboration & Dataset
This research was conducted using historical parcel delivery records from **PT Pos Indonesia KCU Malang**, covering five districts in Kota Malang (July 2024 dataset).
- **Operational Goal:** Transform raw historical delivery manifests (`CSV`/`XLSX`/`XLS`) into balanced, geographically compact courier delivery zones benchmarked against actual field assignments (`Petugas`).
- **Result:** Demonstrated improved workload balance ($Z_1$) while preserving spatial compactness across all five districts.

---

## 📚 Academic Thesis
- **Title:** "Package Delivery Zone Allocation Based on Spatial Proximity and Courier Workload Balance Using K-Means++ and HBCDP"
- **Indonesian Title:** "Pembagian Zona Pengantaran Paket Berdasarkan Kedekatan Spasial dan Keseimbangan Beban Kerja Kurir Menggunakan Algoritma Balanced K-Means"
- **Institution:** State Polytechnic of Malang (*Politeknik Negeri Malang*)
- **Repository:** [GeoKurir Malang Thesis Repository](https://github.com/achmaddoli/RepoSkripsi_AchmadDoliHarahap_4J_RPL.git)

---

## 🛠️ Tech Stack
| Category | Tools & Technologies |
| :--- | :--- |
| **Backend & Web App** | Python, Flask |
| **Clustering & Geospatial** | NumPy, Pandas, Scikit-learn, Shapely (Convex Hull), Planar Meter Projection |
| **Geocoding & Maps** | Google Maps Platform (Geocoding API & Maps JavaScript API) |
| **Database & Admin** | PostgreSQL, Custom Migration Runner (`migrate.py`), Adminer |
| **Containerization & QA** | Docker, Docker Compose (`geokurir-actual`), Python `unittest` |

---

## ⚙️ Installation & System Setup

### 1. Clone Repository

```bash
git clone [https://github.com/achmaddoli/RepoSkripsi_AchmadDoliHarahap_4J_RPL.git](https://github.com/achmaddoli/RepoSkripsi_AchmadDoliHarahap_4J_RPL.git)
cd RepoSkripsi_AchmadDoliHarahap_4J_RPL
```

---

### 2. Configure Environment Variables

Create a `.env` file in the project root and configure your own Google Maps API key for geocoding new addresses (keys and data are never copied automatically from other deployments):

```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
```

---

### 3. Build & Start Containers (Docker Compose)

Run from the project root directory:

```bash
docker compose up -d --build
```

The stack runs under the isolated Compose project `geokurir-actual` with its own PostgreSQL volume (`geokurir-actual_postgres_data`):
- **Web Application:** `http://127.0.0.1:5001`
- **PostgreSQL Host Port:** `5433`
- **Adminer (Database UI):** `http://127.0.0.1:8081`

---

### 4. Database Migrations

The `web` container automatically executes `up` migrations before starting the Flask application. This applies schema additions safely without deleting existing datasets (**do not use `fresh` when upgrading**).

To run or inspect migration status manually:

```bash
docker compose exec -T web python migrate.py up
docker compose exec -T web python migrate.py status
```

---

### 5. Run Unit & Integration Tests

```bash
docker compose exec -T -e GEOKURIR_INTEGRATION_TESTS=1 web python -m unittest discover -s tests -v
```

---

## 🔄 Full System Workflow

### 6. How to Run the Full Workflow

1. Start the Docker Compose stack (`web` and PostgreSQL database)
2. Open `http://127.0.0.1:5001` and upload a parcel dataset (`CSV`, `XLSX`, or `XLS`) with optional **`Petugas`** column
3. System cleans recipient addresses and runs **Google Maps Geocoding**
4. System automatically computes and stores the actual PT Pos baseline in **`evaluasi_aktual`**, displaying baseline metrics on the **Upload** page before clustering starts
5. Set the target number of courier zones ($K$) and start clustering
6. Backend projects coordinates into planar meters and executes:
   - **K-Means++** spatial centroid initialization
   - **HBCDP** iterative workload balancing (with runtime measured strictly from K-Means++ start to HBCDP completion)
7. Inspect interactive **Google Maps** delivery zones, **Aktual PT Pos Zone** comparison, and **Evaluation** metrics (**Silhouette Score, DBI, $Z_1$, $Z_2$**)
8. Export clustered assignments enriched with **`Petugas Aktual`**

---

## 📌 Notes

- Each deployment requires its own `GOOGLE_MAPS_API_KEY` in `.env` to geocode newly uploaded addresses.
- Updating geocoded coordinates or `Petugas` labels updates the data fingerprint and refreshes `evaluasi_aktual`, whereas changing $K$ alone re-runs clustering without recomputing the actual baseline.

---

## 📺 Visuals & Interface

### 💻 Web Application Interface
*The system provides an end-to-end geospatial workflow across 6 core views: Dashboard Overview, Dataset Upload, Data Processing & Geocoding, Delivery Zone Results, Clustering Evaluation, and Dataset Management.*

| 📊 Dashboard Overview | 📤 Upload Dataset | ⚙️ Data Processing & Geocoding |
| :---: | :---: | :---: |
| <img src="public/dashboard.png" width="250" alt="Dashboard Overview"> | <img src="public/upload.png" width="250" alt="Upload Dataset"> | <img src="public/processing.png" width="250" alt="Data Processing and Geocoding"> |
| **🗺️ Delivery Zone Results** | **⚖️ Clustering Evaluation** | **🗂️ Manage Datasets** |
| <img src="public/zones.png" width="250" alt="Delivery Zone Results"> | <img src="public/evaluation.png" width="250" alt="Clustering Evaluation"> | <img src="public/manage_dataset.png" width="250" alt="Manage Datasets"> |

---

## 📈 Learning Journey
### **⚠️ Challenges & How I Overcame Them**

#### 1. Geocoding Accuracy & Spatial Boundary Control
- **Challenge:** Raw historical delivery records contained inconsistent address formats and abbreviations that could produce inaccurate coordinates or overly stretched clusters.
- **Solution:** I implemented address cleaning and boundary validation prior to clustering, and calibrated the HBCDP maximum distance threshold ($D = 5,285.15\text{ m}$) using the mean distance across Kota Malang's five subdistrict centroids so balanced zones remain geographically compact.

#### 2. Edge-Case Geometries in Zone Boundary Rendering
- **Challenge:** When evaluating higher values of $K$, clusters containing only one or two delivery points caused Shapely's `.convex_hull` to return a `Point` or `LineString` instead of a `Polygon`, triggering attribute errors during boundary rendering.
- **Solution:** I added explicit `geom_type` handling in the spatial visualization pipeline to render polygons, line segments, and single-point zones cleanly on the map.

### **What I Learned**
Building this end-to-end system strengthened my understanding of how **machine learning algorithms must be adapted to real operational constraints**. I learned that mathematical cluster validity alone is not enough—translating research into a production-ready tool requires fair baseline benchmarking, strict null/edge-case handling, reproducible database migrations, and clear visual diagnostics that operational teams can trust.
