import math
import collections
import numpy as np
from shapely.geometry import MultiPoint, Point, LineString, Polygon
from sklearn.metrics import silhouette_score, davies_bouldin_score

EPS_Z1 = 1e-6
EPS_Z2 = 1e-6

class HBCDPService:
    """
    HBCDPService mengimplementasikan 100% algoritma Calvete, Galé & Iranzo
    sesuai modul riset Bab II & Bab III Notebook 17_Oktober_2026.ipynb:
      - Algorithm 1 : Step 1 direct reassignment (memperbaiki Z1)
      - Algorithm 2 : Step 2 path reassignment dengan BFS (memperbaiki Z1)
      - Algorithm 3 : Step 3 pairwise exchange (memperbaiki Z2 dengan cardinality tetap)
      - Algorithm 4 : Step 4 negative cycle/path dengan Bellman-Ford (memperbaiki Z2 lanjutan)
    """

    def __init__(self, d_max: float =  5285.15):
        self.d_max = float(d_max)

    # ------------------------------------------------------------------------
    # 1. Geometri Convex Hull & Batas Zona (Shapely)
    # ------------------------------------------------------------------------

    def _shapely_geom_boundary(self, boundary):
        """Membangun geometri Shapely dari array batas koordinat."""
        b = np.asarray(boundary, dtype=float).reshape(-1, 2)
        if len(b) == 0:
            raise ValueError("Zona kosong tidak diperbolehkan.")
        if len(b) == 1:
            return Point(b[0])
        if len(b) == 2:
            return LineString(b)
        return Polygon(b)

    def _shapely_boundary_lines(self, geom):
        """Batas polygon = LineString perimeter; segmen/titik = geometri itu sendiri."""
        return geom.boundary if geom.geom_type == "Polygon" else geom

    def build_hbcdp_zone_boundaries(self, X, initial_labels, K):
        """
        Convex Hull Shapely untuk tiap cluster awal (C_j);
        statis selama proses HBCDP sesuai semantik Calvete.
        """
        X = np.asarray(X, dtype=float)
        labels0 = np.asarray(initial_labels, dtype=int)
        bounds = {}
        for j in range(K):
            pts = X[labels0 == j]
            if len(pts) == 0:
                raise ValueError(f"Cluster awal C{j+1} kosong; boundary HBCDP tidak dapat dibentuk.")
            geometry = MultiPoint([tuple(xy) for xy in pts]).convex_hull
            if geometry.geom_type == "Polygon":
                coords = np.asarray(geometry.exterior.coords[:-1], dtype=float)
            elif geometry.geom_type == "LineString":
                coords = np.asarray(geometry.coords, dtype=float)
            elif geometry.geom_type == "Point":
                coords = np.asarray([geometry.coords[0]], dtype=float)
            else:
                coords = np.asarray(pts, dtype=float)
            bounds[j] = coords.reshape(-1, 2)
        return bounds

    def distance_point_to_zone_boundary(self, point, boundary):
        """
        d_ij: Jarak Euclidean ke sisi terdekat dari zona tujuan (perimeter).
        """
        geo = self._shapely_geom_boundary(boundary)
        p = Point(np.asarray(point, dtype=float))
        return float(p.distance(self._shapely_boundary_lines(geo)))

    def build_hbcdp_distance_matrix(self, X, boundaries, initial_labels, K):
        """
        Matriks statis d_ij (N x K) mengikuti semantik Calvete:
        - jika customer i pre-assigned ke cluster j, d_ij = 0.0;
        - untuk cluster lain, d_ij = jarak Euclidean customer i ke line segment terdekat zona j.
        """
        X = np.asarray(X, dtype=float)
        initial_labels = np.asarray(initial_labels, dtype=int)
        N = len(X)
        Dm = np.zeros((N, K), dtype=float)
        for i, point in enumerate(X):
            for j in range(K):
                if int(initial_labels[i]) == j:
                    Dm[i, j] = 0.0
                else:
                    Dm[i, j] = self.distance_point_to_zone_boundary(point, boundaries[j])
        return Dm

    def distance_between_zone_boundaries(self, boundary_a, boundary_b):
        """Δ_jk: minimum jarak antar batas geometris dua zona."""
        ga = self._shapely_boundary_lines(self._shapely_geom_boundary(boundary_a))
        gb = self._shapely_boundary_lines(self._shapely_geom_boundary(boundary_b))
        return float(ga.distance(gb))

    def build_hbcdp_cluster_distance_matrix(self, boundaries, K):
        """Matriks Δ_jk untuk pengurutan cluster target k pada Algorithm 1."""
        Delta = np.zeros((K, K), dtype=float)
        for j in range(K):
            for k in range(j + 1, K):
                d = self.distance_between_zone_boundaries(boundaries[j], boundaries[k])
                Delta[j, k] = Delta[k, j] = d
        return Delta

    # ------------------------------------------------------------------------
    # 2. Perhitungan Metrik Evaluasi Z1, Z2, Centroid
    # ------------------------------------------------------------------------

    def compute_z1(self, labels, K):
        """Variansi ukuran klaster (Z1) sesuai Persamaan (2.37)."""
        counts = np.bincount(np.asarray(labels, dtype=int), minlength=K)
        mean_n = np.mean(counts)
        return float(np.mean((counts - mean_n) ** 2))

    def compute_z2(self, labels, d_matrix):
        """
        Z2 Calvete: Σ_i d_i,label(i) sesuai Persamaan (2.38).
        d_ij adalah jarak ke batas zona Convex Hull yang telah dibentuk di awal.
        """
        labels_arr = np.asarray(labels, dtype=int)
        return float(np.sum(d_matrix[np.arange(len(labels_arr)), labels_arr]))

    def calculate_cluster_centroids(self, X, labels, K):
        """Menghitung posisi titik pusat (centroid) klaster."""
        X = np.asarray(X, dtype=float)
        labels_arr = np.asarray(labels, dtype=int)
        centroids = np.zeros((K, X.shape[1]), dtype=float)
        for k in range(K):
            pts = X[labels_arr == k]
            if len(pts) > 0:
                centroids[k] = pts.mean(axis=0)
        return centroids

    
    def convexHull(self, points):
        """
        Menghasilkan Convex Hull untuk visualisasi:
        - 1 titik: Point
        - 2 titik atau kolinear: LineString
        - 3+ titik tidak kolinear: Polygon tertutup
        """
        if len(points) == 0:
            return []

        pts = np.asarray(points, dtype=float).reshape(-1, 2)
        geometry = MultiPoint([tuple(p) for p in pts]).convex_hull

        if geometry.geom_type == "Polygon":
            return [
                [float(x), float(y)]
                for x, y in geometry.exterior.coords
            ]

        if geometry.geom_type == "LineString":
            return [
                [float(x), float(y)]
                for x, y in geometry.coords
            ]

        if geometry.geom_type == "Point":
            return [[float(geometry.x), float(geometry.y)]]

        return []

    # ------------------------------------------------------------------------
    # 3. Eksekusi 4 Tahap Calvete et al. (Algorithm 1 s.d. 4)
    # ------------------------------------------------------------------------

    def run_hbcdp(self, X, initial_labels, initial_centroids, K, D_limit):
        """
        Implementasi lengkap Calvete, Galé & Iranzo:
          Algorithm 1 : Step 1 direct reassignment (improve Z1)
          Algorithm 2 : Step 2 path reassignment dengan BFS (improve Z1)
          Algorithm 3 : Step 3 pairwise exchange (improve Z2, cardinality fixed)
          Algorithm 4 : Step 4 negative cycle/path dengan Bellman-Ford
        """
        X = np.asarray(X, dtype=float)
        N = len(X)
        initial_labels = np.asarray(initial_labels, dtype=int)
        initial_centroids = np.asarray(initial_centroids, dtype=float)

        # 1. Bentuk zona statis dan matriks jarak d_ij & Delta_jk
        boundaries = self.build_hbcdp_zone_boundaries(X, initial_labels, K)
        d_matrix = self.build_hbcdp_distance_matrix(X, boundaries, initial_labels, K)
        cluster_distance = self.build_hbcdp_cluster_distance_matrix(boundaries, K)

        labels = initial_labels.copy()
        centroids = initial_centroids.copy()
        C_sizes = np.bincount(initial_labels, minlength=K)

        # Matriks penugasan biner x[i, j] = 1 jika customer i pada cluster j
        x = np.zeros((N, K), dtype=np.int8)
        x[np.arange(N), labels] = 1

        snapshots = {}
        audit_trail = []

        def d(i, j):
            return float(d_matrix[i, j])

        def counts_now():
            return x.sum(axis=0).astype(int)

        def sync_labels_from_x():
            nonlocal labels
            labels = np.argmax(x, axis=1).astype(int)

        def reassign_customer(i, j, k):
            x[i, j] = 0
            x[i, k] = 1
            labels[i] = k

        def feasible_customers(j, k):
            return [int(i) for i in np.where(x[:, j] == 1)[0] if d(int(i), k) <= D_limit]

        def m_matrix():
            M = np.zeros((K, K), dtype=int)
            for j in range(K):
                for k in range(K):
                    if j != k:
                        M[j, k] = len(feasible_customers(j, k))
            return M

        def best_customer(j, k):
            cand = feasible_customers(j, k)
            if not cand:
                return None
            return min(cand, key=lambda i: (d(i, k) - d(i, j), i))

        def g_matrix():
            G = np.full((K, K), np.inf, dtype=float)
            Ibest = {}
            for j in range(K):
                for k in range(K):
                    if j == k:
                        continue
                    i = best_customer(j, k)
                    if i is not None:
                        G[j, k] = d(i, k) - d(i, j)
                        Ibest[(j, k)] = i
            return G, Ibest

        def save_snapshot(stage):
            cc = counts_now()
            st_centroids = self.calculate_cluster_centroids(X, labels, K)
            unique_labels = np.unique(labels)
            sil = 0.0
            dbi = 0.0
            if len(unique_labels) >= 2 and len(unique_labels) < len(X):
                try:
                    sil = float(silhouette_score(X, labels))
                    dbi = float(davies_bouldin_score(X, labels))
                except Exception:
                    pass
            snapshots[stage] = {
                "labels": labels.copy().tolist(),
                "centroids": [[round(float(c[0]), 2), round(float(c[1]), 2)] for c in st_centroids],
                "cardinality": cc.copy().tolist(),
                "Z1": round(self.compute_z1(labels, K), 4),
                "Z2": round(self.compute_z2(labels, d_matrix), 2),
                "Silhouette": round(sil, 4),
                "DBI": round(dbi, 4),
                "N_Changed": int(np.sum(labels != initial_labels))
            }

        save_snapshot("Initial")

        # --------------------------------------------------------------------
        # ALGORITHM 1 — STEP 1 (Direct Reassignment)
        # --------------------------------------------------------------------
        while True:
            changed = False
            for j in sorted(range(K), key=lambda q: (C_sizes[q], q)):
                k_order = sorted([k for k in range(K) if k != j],
                                 key=lambda k: (cluster_distance[j, k], k))
                for k in k_order:
                    y = counts_now()
                    if y[j] - y[k] > 1:
                        cand = feasible_customers(j, k)
                        m_jk = len(cand)
                        r = min(m_jk, (int(y[j]) - int(y[k])) // 2)
                        for _ in range(r):
                            i = best_customer(j, k)
                            if i is None:
                                break
                            reassign_customer(i, j, k)
                            changed = True
            if not changed:
                break

        save_snapshot("Step 1")

        # --------------------------------------------------------------------
        # ALGORITHM 2 — STEP 2 (Path Reassignment dengan BFS)
        # --------------------------------------------------------------------
        while True:
            any_reassignment = False
            for j in sorted(range(K), key=lambda q: (C_sizes[q], q)):
                M = m_matrix()
                adj = {u: [v for v in range(K) if u != v and M[u, v] > 0] for u in range(K)}

                y = counts_now()
                pred = {j: None}
                queue = collections.deque([j])
                endpoint = None
                while queue and endpoint is None:
                    u = queue.popleft()
                    for v in adj[u]:
                        if v not in pred:
                            pred[v] = u
                            if y[j] - y[v] > 1:
                                endpoint = v
                                break
                            queue.append(v)

                if endpoint is None:
                    continue

                path = []
                cur = endpoint
                while cur is not None:
                    path.append(cur)
                    cur = pred[cur]
                path.reverse()

                caps = [M[path[t], path[t + 1]] for t in range(len(path) - 1)]
                r = min(min(caps), (int(y[path[0]]) - int(y[path[-1]])) // 2)
                if r < 1:
                    continue

                for t in range(len(path) - 1, 0, -1):
                    u, v = path[t - 1], path[t]
                    for _ in range(r):
                        i = best_customer(u, v)
                        if i is None:
                            break
                        reassign_customer(i, u, v)
                        any_reassignment = True
            if not any_reassignment:
                break

        z1_fixed = self.compute_z1(labels, K)
        save_snapshot("Step 2")

        # --------------------------------------------------------------------
        # ALGORITHM 3 — STEP 3 (Pairwise Exchange)
        # --------------------------------------------------------------------
        while True:
            changed = False
            for j in sorted(range(K), key=lambda q: (C_sizes[q], q)):
                G, Ibest = g_matrix()
                options = [(G[j, k] + G[k, j], k) for k in range(K) if k != j
                           and np.isfinite(G[j, k]) and np.isfinite(G[k, j])]
                if not options:
                    continue
                pair_cost, k = min(options, key=lambda z: (z[0], z[1]))
                if pair_cost < -EPS_Z2:
                    i_jk = Ibest[(j, k)]
                    i_kj = Ibest[(k, j)]
                    x[i_jk, j], x[i_jk, k] = 0, 1
                    x[i_kj, k], x[i_kj, j] = 0, 1
                    sync_labels_from_x()
                    changed = True
            if not changed:
                break

        save_snapshot("Step 3")

        # --------------------------------------------------------------------
        # ALGORITHM 4 — STEP 4 (Multiple Exchange via Bellman-Ford)
        # --------------------------------------------------------------------
        def bellman_ford_from(source, Gcost):
            edges = [(u, v, float(Gcost[u, v])) for u in range(K) for v in range(K)
                     if u != v and np.isfinite(Gcost[u, v])]
            dist = [float("inf")] * K
            pred = [None] * K
            dist[source] = 0.0
            for _ in range(K - 1):
                updated = False
                for u, v, w in edges:
                    if np.isfinite(dist[u]) and dist[u] + w < dist[v] - EPS_Z2:
                        dist[v] = dist[u] + w
                        pred[v] = u
                        updated = True
                if not updated:
                    break

            cycle_vertex = None
            for u, v, w in edges:
                if np.isfinite(dist[u]) and dist[u] + w < dist[v] - EPS_Z2:
                    pred[v] = u
                    cycle_vertex = v
                    break
            return dist, pred, cycle_vertex

        def recover_negative_cycle(pred, v):
            if v is None:
                return None
            q = v
            for _ in range(K):
                if q is None:
                    return None
                q = pred[q]
            start_cycle = q
            rev = [start_cycle]
            q = pred[start_cycle]
            while q is not None and q != start_cycle and len(rev) <= K + 1:
                rev.append(q)
                q = pred[q]
            if q != start_cycle:
                return None
            return list(reversed(rev))

        def recover_path(pred, source, target):
            path = [target]
            q = target
            while q != source:
                q = pred[q]
                if q is None:
                    return None
                path.append(q)
                if len(path) > K + 1:
                    return None
            return list(reversed(path))

        while True:
            some_reassignment = False
            for j in sorted(range(K), key=lambda q: (C_sizes[q], q)):
                G, _ = g_matrix()
                dist, pred, neg_v = bellman_ford_from(j, G)

                cycle = recover_negative_cycle(pred, neg_v)
                if cycle and len(cycle) >= 2:
                    for t in range(len(cycle)):
                        u = cycle[t]
                        v = cycle[(t + 1) % len(cycle)]
                        i = best_customer(u, v)
                        if i is None:
                            break
                        reassign_customer(i, u, v)
                    some_reassignment = True
                    break

                y = counts_now()
                endpoints = [k for k in range(K) if k != j and np.isfinite(dist[k])
                             and dist[k] < -EPS_Z2 and y[j] - y[k] == 1]
                if endpoints:
                    k = min(endpoints, key=lambda q: (dist[q], q))
                    path = recover_path(pred, j, k)
                    if path and len(path) >= 2:
                        for t in range(len(path) - 1, 0, -1):
                            u, v = path[t - 1], path[t]
                            i = best_customer(u, v)
                            if i is None:
                                break
                            reassign_customer(i, u, v)
                        some_reassignment = True
                        break

            if not some_reassignment:
                break

        save_snapshot("Step 4")
        final_centroids = self.calculate_cluster_centroids(X, labels, K)
        return labels, final_centroids, boundaries, snapshots

    # ------------------------------------------------------------------------
    # 4. Entry Point Lengkap untuk Backend Flask
    # ------------------------------------------------------------------------

    def optimasi(self, points, initial_labels, centroids, k: int = 5):
        """
        Eksekusi lengkap alur 4 tahap optimasi HBCDP untuk dipanggil oleh REST API.
        """
        X = np.asarray(points, dtype=float)
        labels_fin, centroids_fin, boundaries, snapshots = self.run_hbcdp(
            X=X,
            initial_labels=initial_labels,
            initial_centroids=centroids,
            K=k,
            D_limit=self.d_max
        )

        init_snap = snapshots.get("Initial", {})
        s1 = snapshots.get("Step 1", {})
        s2 = snapshots.get("Step 2", {})
        s3 = snapshots.get("Step 3", {})
        s4 = snapshots.get("Step 4", {})

        # Hitung jumlah titik yang berubah dibanding tahap sebelumnya
        def hitung_titik_berubah(snapshot_sekarang, snapshot_sebelumnya):
            labels_sekarang = np.asarray(
                snapshot_sekarang["labels"], dtype=int
            )
            labels_sebelumnya = np.asarray(
                snapshot_sebelumnya["labels"], dtype=int
            )

            if labels_sekarang.shape != labels_sebelumnya.shape:
                raise ValueError(
                    "Jumlah titik antar snapshot HBCDP tidak sama."
                )

            return int(np.sum(labels_sekarang != labels_sebelumnya))

        # Format steps array untuk frontend
        steps_summary = [
            {
                "step": "Step 1",
                "nama": "Direct Reassignment",
                "cardinality": str(s1.get("cardinality", [])),
                "z1": str(s1.get("Z1", 0.0)),
                "z2": f"{s1.get('Z2', 0.0):,.2f} m".replace(",", "X").replace(".", ",").replace("X", "."),
                "reassigned": hitung_titik_berubah(s1, init_snap)
            },
            {
                "step": "Step 2",
                "nama": "Path Reassignment (BFS)",
                "cardinality": str(s2.get("cardinality", [])),
                "z1": str(s2.get("Z1", 0.0)),
                "z2": f"{s2.get('Z2', 0.0):,.2f} m".replace(",", "X").replace(".", ",").replace("X", "."),
                "reassigned": hitung_titik_berubah(s2, s1)
            },
            {
                "step": "Step 3",
                "nama": "Pairwise Exchange",
                "cardinality": str(s3.get("cardinality", [])),
                "z1": str(s3.get("Z1", 0.0)),
                "z2": f"{s3.get('Z2', 0.0):,.2f} m".replace(",", "X").replace(".", ",").replace("X", "."),
                "reassigned": hitung_titik_berubah(s3, s2)
            },
            {
                "step": "Step 4",
                "nama": "Multiple Exchange (Bellman-Ford)",
                "cardinality": str(s4.get("cardinality", [])),
                "z1": str(s4.get("Z1", 0.0)),
                "z2": f"{s4.get('Z2', 0.0):,.2f} m".replace(",", "X").replace(".", ",").replace("X", "."),
                "reassigned": hitung_titik_berubah(s4, s3)
            }
        ]

        # Konversi boundaries untuk visualisasi Convex Hull
        hull_polygons = {}
        for c_idx in range(k):
            c_pts = X[labels_fin == c_idx]
            if len(c_pts) > 0:
                hull_polygons[c_idx] = self.convexHull(c_pts.tolist())
            else:
                hull_polygons[c_idx] = []

        # Bentuk data zona_kurir untuk persistensi database PostgreSQL
        zonas_list = []
        c_card = s4.get("cardinality", [])
        for c_idx in range(k):
            poly_coords = hull_polygons.get(c_idx, [])
            if len(poly_coords) >= 3:
                poly_wkt = f"POLYGON(({', '.join(f'{p[0]} {p[1]}' for p in poly_coords)}))"
            elif len(poly_coords) == 2:
                poly_wkt = f"LINESTRING({', '.join(f'{p[0]} {p[1]}' for p in poly_coords)})"
            elif len(poly_coords) == 1:
                poly_wkt = f"POINT({poly_coords[0][0]} {poly_coords[0][1]})"
            else:
                poly_wkt = "GEOMETRYCOLLECTION EMPTY"
            zonas_list.append({
                "nomor_zona": c_idx + 1,
                "jumlah_anggota": int(c_card[c_idx]) if c_idx < len(c_card) else 0,
                "polygon": poly_wkt
            })

        return {
            "final_labels": labels_fin.tolist(),
            "final_centroids": [[round(float(c[0]), 2), round(float(c[1]), 2)] for c in centroids_fin],
            "initial_z1": init_snap.get("Z1", 0.0),
            "initial_z2": init_snap.get("Z2", 0.0),
            "final_z1": s4.get("Z1", 0.0),
            "final_z2": s4.get("Z2", 0.0),
            "z1_final": s4.get("Z1", 0.0),
            "z2_final": s4.get("Z2", 0.0),
            "silhouette": s4.get("Silhouette", 0.0),
            "dbi": s4.get("DBI", 0.0),
            "cardinality": s4.get("cardinality", []),
            "steps": steps_summary,
            "boundaries": hull_polygons,
            "zonas": zonas_list
        }
