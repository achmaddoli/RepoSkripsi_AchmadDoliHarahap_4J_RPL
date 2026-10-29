import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score

class KMeansService:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    def hitungJarakEuclidean(self, p1, p2):
        """Menghitung jarak Euclidean antara dua titik (x, y)."""
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        return float(np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))

    def clustering(self, points, k: int):
        """
        Menjalankan algoritma K-Means clustering (KMeans++).
        points: list of tuple/list [(x1, y1), (x2, y2), ...] dalam meter
        k: jumlah cluster (kurir)
        Returns: { 'labels': [0, 1, ...], 'centroids': [[x, y], ...], 'counts': [c1, c2, ...] }
        """
        X = np.asarray(points, dtype=float)
        n = len(X)
        if n == 0 or k <= 0:
            return {"labels": [], "centroids": [], "counts": []}

        if n <= k:
            labels = list(range(n))
            centroids = [list(X[i]) for i in range(n)]
            counts = [1] * n
            return {"labels": labels, "centroids": centroids, "counts": counts}

        kmeans = KMeans(
            n_clusters=k,
            init="k-means++",
            random_state=self.random_state,
            n_init=10
        )
        labels = kmeans.fit_predict(X).astype(int)
        centroids = kmeans.cluster_centers_

        counts = np.bincount(labels, minlength=k).tolist()
        return {
            "labels": labels.tolist(),
            "centroids": [[round(float(c[0]), 2), round(float(c[1]), 2)] for c in centroids],
            "counts": counts
        }

    def hitungCentroid(self, points):
        """Menghitung centroid dari sekelompok titik."""
        if not points:
            return [0.0, 0.0]
        pts = np.asarray(points, dtype=float)
        return [round(float(pts[:, 0].mean()), 2), round(float(pts[:, 1].mean()), 2)]

    def evaluasiCluster(self, points, labels, centroids, k: int):
        """
        Evaluasi metrik cluster sesuai formula Bab II & Bab III notebook:
        - Silhouette Score (Persamaan 2.33)
        - Davies-Bouldin Index (Persamaan 2.34-2.36)
        - Z1 variansi cardinality (Persamaan 2.37)
        """
        X = np.asarray(points, dtype=float)
        labels_arr = np.asarray(labels, dtype=int)
        unique_labels = np.unique(labels_arr)

        sil = 0.0
        dbi = 0.0
        if len(unique_labels) >= 2 and len(unique_labels) < len(X):
            try:
                sil = float(silhouette_score(X, labels_arr))
                dbi = float(davies_bouldin_score(X, labels_arr))
            except Exception:
                pass

        counts = np.bincount(labels_arr, minlength=k)
        mean_n = np.mean(counts)
        z1 = float(np.mean((counts - mean_n) ** 2))
        

        return {
            "silhouette_score": round(sil, 4),
            "dbi": round(dbi, 4),
            "z1": round(z1, 4),
            "cardinality": counts.tolist()
        }
