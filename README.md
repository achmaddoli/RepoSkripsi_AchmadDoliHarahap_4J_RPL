# 📦 Spatial Package Delivery Zone Clustering Using Balanced K-Means

<p align="center">
  <img src="https://img.shields.io/badge/Field-Machine_Learning-blue?style=for-the-badge" alt="Machine Learning">
  <img src="https://img.shields.io/badge/Method-Balanced_K--Means-orange?style=for-the-badge" alt="Balanced K-Means">
  <img src="https://img.shields.io/badge/Domain-Geospatial_Analytics-green?style=for-the-badge" alt="Geospatial Analytics">
</p>

## 🧠 Why I Built This

Last-mile delivery is not only about assigning packages to couriers — it is also about ensuring that each courier receives a geographically reasonable and balanced delivery area.

At **PT Pos Indonesia KCU Malang**, courier delivery areas can change depending on the daily distribution of packages. When delivery points are geographically scattered or workload distribution becomes uneven, couriers may need to cover areas that are farther apart while handling different numbers of packages.

This led me to a key question:

> *How can package delivery points be grouped into geographically compact zones while maintaining a balanced workload among couriers?*

To address this problem, I developed a spatial clustering approach using **Balanced K-Means**, combining geographic proximity with workload-balancing constraints.

---

## 🎯 Project Context

* **Type:** Undergraduate Final Thesis
* **Field:** Applied Informatics Engineering / Machine Learning
* **Research Area:** Geospatial Clustering & Last-Mile Delivery
* **Role:** Researcher & System Developer
* **Institution:** State Polytechnic of Malang
* **Research Object:** PT Pos Indonesia KCU Malang
* **Algorithm:** Balanced K-Means
* **Distance Metric:** Euclidean Distance

---

## 👨‍💻 My Contribution

As the individual researcher and developer of this project, I designed the complete research and system workflow, including:

* historical delivery-data preprocessing
* recipient-address cleaning
* address geocoding
* geographic coordinate validation
* coordinate transformation for spatial distance calculation
* Balanced K-Means implementation
* courier workload balancing
* cluster evaluation
* spatial visualization of delivery zones
* interpretation of clustering results for operational recommendations

The system was designed to transform raw historical delivery records into structured geographic delivery zones that can support courier-area planning.

---

## ⚙️ My Approach (How I Think)

Instead of applying standard clustering directly to package locations, I focused on three principles.

### 1. Spatial Proximity Over Arbitrary Assignment

Courier zones should represent geographically meaningful areas.

➡️ I used **geographic coordinates derived from recipient addresses** and calculated spatial proximity using **Euclidean Distance** after coordinate transformation.

This allows delivery points located closer to each other to be grouped within the same delivery zone.

---

### 2. Balance Over Standard Clustering

Standard K-Means primarily minimizes the distance between points and cluster centroids, but it does not guarantee that cluster sizes are balanced.

➡️ I implemented **Balanced K-Means** to simultaneously consider:

* spatial compactness
* courier workload distribution
* cluster capacity constraints

The objective is to prevent situations where one courier receives significantly more delivery points than another.

---

### 3. Operational Relevance Over Pure Algorithmic Results

A clustering result is only useful if it can be interpreted operationally.

➡️ I designed the output as **visual delivery zones and cluster summaries**, making it easier to analyze:

* package distribution
* courier workload
* cluster coverage
* spatial relationships between delivery points

---

## 📌 Project Overview

This project develops a **geospatial clustering system for package delivery-zone allocation** using the Balanced K-Means algorithm.

Historical package-delivery data from PT Pos Indonesia KCU Malang is processed and transformed into geographic coordinates. The delivery locations are then grouped into balanced spatial clusters representing recommended courier delivery zones.

The system combines:

**Delivery Data → Geocoding → Spatial Transformation → Balanced K-Means → Cluster Evaluation → Interactive Visualization**

---

## 🚀 Key Features

* **📍 Address Geocoding:** Converts recipient addresses into latitude and longitude coordinates.
* **🗺️ Spatial Data Processing:** Validates and transforms geographic coordinates for clustering.
* **🧠 Balanced K-Means Clustering:** Generates geographically compact delivery zones while maintaining balanced cluster sizes.
* **📏 Euclidean Distance:** Measures spatial proximity between delivery points and cluster centroids.
* **⚖️ Workload Balancing:** Controls the distribution of delivery points across courier zones.
* **📊 Cluster Evaluation:** Evaluates both clustering quality and workload distribution.
* **🗺️ Interactive Mapping:** Displays delivery points, cluster assignments, and delivery zones spatially.
* **📑 Cluster Summary:** Provides operational summaries for each generated delivery zone.

---

## 🧠 Design Reasoning

### **The Problem: Dynamic Courier Delivery Areas**

Package distribution changes from day to day.

Because courier assignments depend on the distribution of incoming packages, delivery areas may not always remain geographically compact or evenly distributed.

This creates two important challenges:

* delivery points assigned to the same courier may be geographically dispersed
* the number of packages handled by each courier may become uneven

---

### **The Research: Beyond Standard K-Means**

Traditional K-Means is effective for grouping geographically similar points because it minimizes the distance between data points and their cluster centroid.

However, standard K-Means does not explicitly control the number of points assigned to each cluster.

For courier delivery-zone allocation, this limitation is important because a spatially compact cluster can still result in an uneven workload.

Therefore, this research applies **Balanced K-Means**, where cluster assignments consider both geographic proximity and balancing constraints.

---

### **The Solution: Why Balanced K-Means?**

#### 1. Spatial Compactness

Delivery points are grouped according to their proximity to cluster centroids using **Euclidean Distance**.

This encourages each courier zone to consist of locations that are geographically close to each other.

#### 2. Balanced Workload

Cluster capacity constraints are introduced so that delivery points are distributed more evenly across the available couriers.

This prevents highly unbalanced cluster sizes.

#### 3. Operational Visualization

The clustering results are displayed through geographic visualization, allowing each recommended zone to be inspected spatially rather than only through numerical outputs.

---

## 🔬 Research Workflow

### 1. Historical Delivery Data

The research uses historical delivery records from **PT Pos Indonesia KCU Malang**.

The main attributes used include:

* delivery date
* recipient address
* courier information
* package delivery records
* geographic coordinates generated through geocoding

The research focuses on delivery data from **July 2024** within the operational area of PT Pos Indonesia KCU Malang.

---

### 2. Data Cleaning

Raw address data is cleaned before geocoding.

The preprocessing process includes:

* handling missing values
* standardizing address formats
* removing unnecessary characters
* checking duplicate records
* validating administrative-area information

---

### 3. Address Geocoding

Recipient addresses are converted into geographic coordinates.

```text
Recipient Address
        ↓
Address Cleaning
        ↓
Geocoding
        ↓
Latitude & Longitude
        ↓
Coordinate Validation
```

These coordinates represent the spatial position of each package-delivery point.

---

### 4. Coordinate Transformation

Latitude and longitude are geographic coordinates expressed in angular units.

Because Balanced K-Means relies on distance calculations, the coordinates are transformed into an appropriate planar representation before Euclidean Distance is applied.

The Euclidean distance between delivery point \(p_i\) and centroid \(c_k\) is:

```text
d(pi, ck) = √((xi - xk)² + (yi - yk)²)
```

---

### 5. Balanced K-Means Clustering

The clustering process follows several stages:

```text
Delivery Coordinates
        ↓
Initialize Cluster Centroids
        ↓
Calculate Euclidean Distances
        ↓
Balanced Assignment
        ↓
Update Centroids
        ↓
Check Convergence
        ↓
Final Delivery Zones
```

Unlike standard K-Means, the assignment stage also considers the maximum or target capacity of each cluster.

This ensures that the resulting clusters remain relatively balanced.

---

## ⚖️ Balanced Assignment Concept

Assume:

```text
n = total delivery points
K = number of active couriers
```

The expected cluster size can be approximated as:

```text
Target Cluster Size ≈ n / K
```

When the number of points cannot be divided equally, the remaining points are distributed across several clusters while maintaining the smallest possible workload difference.

Example:

```text
100 delivery points
6 couriers

Possible distribution:

17
17
17
17
16
16
```

instead of an unconstrained result such as:

```text
31
22
18
14
10
5
```

---

## 📊 Evaluation

The clustering results are evaluated from two main perspectives.

### **1. Spatial Clustering Quality**

The spatial structure of the generated clusters can be evaluated using clustering metrics such as:

#### Silhouette Score

Measures how well each delivery point fits within its assigned cluster compared with neighboring clusters.

```text
Range: -1 to 1
```

A higher value generally indicates better cluster separation and cohesion.

#### Davies-Bouldin Index

Measures similarity between clusters based on within-cluster dispersion and between-cluster separation.

```text
Lower value = better cluster separation
```

---

### **2. Workload Balance**

The workload distribution between clusters is analyzed by comparing the number of delivery points assigned to each cluster.

A balanced solution should minimize large differences between cluster sizes.

The distribution can also be evaluated using the standard deviation of cluster sizes.

```text
Lower standard deviation
        ↓
More balanced workload distribution
```

---

## 🗺️ Spatial Visualization

The clustering results are visualized geographically to make the generated zones easier to interpret.

The visualization can display:

* recipient delivery points
* cluster membership
* cluster centroids
* courier delivery zones
* number of delivery points per cluster

Example structure:

```text
Interactive Map
│
├── Cluster 1
│   ├── Delivery Points
│   └── Centroid
│
├── Cluster 2
│   ├── Delivery Points
│   └── Centroid
│
└── Cluster N
    ├── Delivery Points
    └── Centroid
```

---

## 🔄 Full System Workflow

```text
Historical Package Delivery Data
              ↓
        Data Selection
              ↓
        Data Cleaning
              ↓
       Address Geocoding
              ↓
     Coordinate Validation
              ↓
   Coordinate Transformation
              ↓
      Balanced K-Means
              ↓
       Cluster Evaluation
              ↓
  Delivery Zone Visualization
              ↓
 Courier Zone Recommendation
```

---

## 🛠️ Tech Stack

| Category                    | Tools & Technologies                                  |
| :-------------------------- | :---------------------------------------------------- |
| **Programming**             | Python                                                |
| **Data Processing**         | Pandas, NumPy                                         |
| **Machine Learning**        | Scikit-learn / Custom Balanced K-Means Implementation |
| **Geospatial Processing**   | GeoPandas, Shapely                                    |
| **Geocoding**               | OpenStreetMap / Nominatim                             |
| **Distance Metric**         | Euclidean Distance                                    |
| **Mapping**                 | Leaflet / Folium                                      |
| **Data Visualization**      | Matplotlib                                            |
| **Development Environment** | Google Colab / Jupyter Notebook                       |
| **Data Format**             | CSV                                                   |

---

## 📂 Project Structure

```text
balanced-kmeans-delivery-zones/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── geocoded/
│
├── notebooks/
│   ├── data_preparation.ipynb
│   ├── geocoding.ipynb
│   ├── balanced_kmeans.ipynb
│   └── evaluation.ipynb
│
├── src/
│   ├── preprocessing.py
│   ├── geocoding.py
│   ├── balanced_kmeans.py
│   ├── evaluation.py
│   └── visualization.py
│
├── results/
│   ├── clusters/
│   ├── evaluation/
│   └── maps/
│
├── requirements.txt
├── README.md
└── LICENSE
```

---

## ⚙️ Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/balanced-kmeans-delivery-zones.git
cd balanced-kmeans-delivery-zones
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Activate the environment.

Windows:

```bash
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Example dependencies:

```text
numpy
pandas
scikit-learn
geopandas
shapely
folium
matplotlib
geopy
```

---

## ▶️ Running the Project

The complete workflow can be executed sequentially.

### Step 1 — Data Preparation

Prepare and clean the historical delivery dataset.

```bash
python src/preprocessing.py
```

---

### Step 2 — Geocoding

Convert recipient addresses into geographic coordinates.

```bash
python src/geocoding.py
```

---

### Step 3 — Balanced K-Means

Run the spatial clustering process.

```bash
python src/balanced_kmeans.py
```

---

### Step 4 — Evaluation

Calculate clustering and workload-balancing metrics.

```bash
python src/evaluation.py
```

---

### Step 5 — Visualization

Generate spatial visualization of the resulting delivery zones.

```bash
python src/visualization.py
```

---

## 📈 Expected Output

The system produces several outputs:

```text
results/
│
├── clustered_delivery_points.csv
├── cluster_summary.csv
├── clustering_evaluation.csv
└── delivery_zone_map.html
```

### Clustered Delivery Points

Contains:

```text
delivery_id
address
latitude
longitude
cluster
courier
```

### Cluster Summary

Contains information such as:

```text
cluster_id
number_of_delivery_points
centroid_x
centroid_y
```

### Interactive Map

Displays each generated delivery zone and its corresponding package-delivery points.

---

## 📌 Research Scope

This research focuses specifically on:

* historical package-delivery data from PT Pos Indonesia KCU Malang
* package delivery locations within its operational area
* delivery records from July 2024
* geographic proximity between recipient locations
* courier workload balancing
* delivery-zone clustering rather than vehicle routing

The research **does not attempt to determine the optimal sequence of roads or delivery routes**.

Instead, it focuses on answering:

> *Which delivery points should belong to the same courier zone?*

Route optimization can subsequently be performed within each generated zone as a separate optimization problem.

---

## 🧩 Research Contribution

The main contribution of this project is the integration of:

**Spatial Clustering + Workload Balancing + Operational Delivery-Zone Visualization**

Rather than using clustering solely to discover geographic groups, this project applies Balanced K-Means to an operational last-mile delivery problem where both **distance and workload distribution matter**.

The resulting clusters are intended to provide a data-driven reference for courier delivery-zone allocation.

---

## 📚 Research Thesis

**Title:**

> **Package Delivery Zone Allocation Based on Spatial Proximity and Courier Workload Balance Using the Balanced K-Means Algorithm**

**Original Indonesian Title:**

> *Pembagian Zona Pengantaran Paket Berdasarkan Kedekatan Spasial dan Keseimbangan Beban Kerja Kurir Menggunakan Algoritma Balanced K-Means*

**Institution:** State Polytechnic of Malang
**Program:** Applied Informatics Engineering
**Research Object:** PT Pos Indonesia KCU Malang

---

## ⚠️ Challenges & How I Addressed Them

### 1. Inconsistent Recipient Addresses

**Challenge:**
Historical delivery records may contain addresses written in different formats, abbreviations, or incomplete administrative information.

**Approach:**
I implemented address-cleaning and normalization steps before geocoding to improve coordinate consistency.

---

### 2. Geographic Coordinate Accuracy

**Challenge:**
Geocoding results may not always correspond exactly to the intended recipient location.

**Approach:**
Coordinates are validated against the research area's geographic boundaries before being used in clustering.

---

### 3. Spatial Compactness vs. Workload Balance

**Challenge:**
The closest cluster assignment does not always produce balanced workloads.

**Approach:**
Instead of relying solely on conventional K-Means assignment, I applied balancing constraints during the assignment process so that cluster capacities remain controlled.

---

### 4. Translating Clusters into Operational Information

**Challenge:**
Numerical cluster labels alone are difficult for operational users to interpret.

**Approach:**
The final clusters are transformed into geographic visualizations and cluster-level summaries so the spatial distribution of courier zones can be inspected directly.

---

## 🎓 What I Learned

This project strengthened my understanding of how **machine learning algorithms must be adapted to real operational constraints**.

I learned that obtaining mathematically valid clusters is only one part of solving a real-world problem. The results must also consider workload distribution, geographic interpretation, data quality, and operational usability.

Through this project, I developed practical experience in:

* geospatial data processing
* machine learning clustering
* Balanced K-Means
* spatial distance analysis
* geocoding
* data preprocessing
* clustering evaluation
* geographic visualization
* operational problem formulation

Most importantly, this research taught me how to translate a real operational problem into a structured **data-driven decision-support approach**.

---

## 🔮 Future Development

Possible future extensions include:

* road-network-based distance calculations
* vehicle routing optimization within each cluster
* dynamic daily courier allocation
* package-volume and weight-based workload balancing
* traffic-aware delivery-zone generation
* integration with real-time courier tracking
* automated delivery-route recommendation

---

## 👨‍💻 Author

**Achmad Doli Harahap**

Applied Informatics Engineering
State Polytechnic of Malang

**Research Interests:**
Machine Learning · Geospatial Analytics · Intelligent Systems · Internet of Things · Data Analytics
