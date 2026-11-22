"""Mengevaluasi pembagian tugas kurir yang sudah ada tanpa mengubah anggota cluster."""

from collections import Counter
import hashlib
import json

import numpy as np
from sklearn.metrics import davies_bouldin_score, silhouette_score


class ActualEvaluationService:
    """
    Menghitung nilai evaluasi berdasarkan titik pengiriman
    yang berhasil mendapatkan koordinat dari geocoding.

    Koordinat yang digunakan sudah diubah ke satuan meter.

    Nomor cluster dimulai dari 0 sampai K-1 dan harus sesuai
    dengan urutan titik pengiriman.

    Jika kolom Petugas kosong, titik pengiriman tetap digunakan
    dalam proses clustering dan pemeriksaan perubahan data.

    """

    @staticmethod
    def _petugas(point):
        value = point.get("petugas")
        return " ".join(str(value).split()).upper() if value is not None else ""

    def fingerprint(self, points):
        """
        Membuat kode unik untuk mengenali data yang digunakan
        dalam proses evaluasi.

        Kode ini digunakan untuk mendeteksi perubahan data,
        misalnya perubahan nama petugas atau koordinat.

        Urutan data tidak memengaruhi kode yang dihasilkan.
        Jika isi data berubah, hasil evaluasi sebelumnya
        dapat diketahui sudah tidak sesuai dengan data terbaru.

        """
        records = []
        for point in points:
            record = {
                field: str(point[field]) if point.get(field) is not None else None
                for field in ("id_pengiriman", "nosi", "petugas")
            }
            for field in ("x_meter", "y_meter", "latitude", "longitude"):
                value = point.get(field)
                record[field] = float(value).hex() if value is not None else None
            records.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
        payload = json.dumps(sorted(records), ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _metrics(points, labels, k):
        labels = np.asarray(labels, dtype=int)
        counts = np.bincount(labels, minlength=k)
        result = {
            "silhouette_score": None,
            "dbi": None,
            "z1": float(np.var(counts)) if len(points) and k else None,
            "cardinality": counts.tolist(),
            "alasan_na": None,
        }
        if not points:
            result["alasan_na"] = "Tidak ada titik untuk dievaluasi."
            return result

        n_labels = len(np.unique(labels))
        if not 2 <= n_labels < len(points):
            result["alasan_na"] = (
                "Silhouette Score dan DBI memerlukan sedikitnya dua kelompok "
                "terisi dan jumlah kelompok lebih kecil daripada jumlah titik "
                f"(kelompok={n_labels}, titik={len(points)})."
            )
            return result

        try:
            coordinates = np.asarray(
                [[point.get("x_meter"), point.get("y_meter")] for point in points],
                dtype=float,
            )
        except (TypeError, ValueError, OverflowError):
            result["alasan_na"] = "Silhouette Score dan DBI: koordinat meter tidak valid."
            return result
        if not np.isfinite(coordinates).all():
            result["alasan_na"] = "Silhouette Score dan DBI: koordinat meter tidak berhingga atau kosong."
            return result

        reasons = []
        for key, name, metric in (
            ("silhouette_score", "Silhouette Score", silhouette_score),
            ("dbi", "DBI", davies_bouldin_score),
        ):
# DBI menggunakan jarak antar pusat cluster (centroid).
# Jika terdapat centroid yang berada di lokasi yang sama,
# nilai DBI dianggap tidak dapat dihitung (N/A).
            if key == "dbi":
                centroids = np.asarray([
                    coordinates[labels == label].mean(axis=0)
                    for label in np.unique(labels)
                ])
                distances = np.linalg.norm(centroids[:, None] - centroids[None, :], axis=2)
                if np.any(distances[np.triu_indices(n_labels, 1)] == 0):
                    reasons.append("DBI tidak terdefinisi karena centroid kelompok berimpit.")
                    continue
            try:
                value = float(metric(coordinates, labels))
            except (ValueError, FloatingPointError, OverflowError) as exc:
                reasons.append(f"{name} tidak dapat dihitung: {exc}")
                continue
            if np.isfinite(value):
                result[key] = value
            else:
                reasons.append(f"{name} menghasilkan nilai tidak berhingga.")
        result["alasan_na"] = " ".join(reasons) or None
        return result

    def evaluate(self, points):
        """
        Menghitung evaluasi pembagian tugas kurir aktual PT Pos.

        Pengelompokan dilakukan berdasarkan nama Petugas
        yang terdapat pada dataset.

        Hasilnya berupa jumlah kurir aktual, jumlah titik
        pengiriman setiap kurir, Silhouette Score, DBI,
        dan nilai keseimbangan jumlah titik (Z1).
        """
        names = [self._petugas(point) for point in points]
        valid_points = [point for point, name in zip(points, names) if name]
        distribution = Counter(name for name in names if name)
        groups = {name: index for index, name in enumerate(sorted(distribution))}
        labels = [groups[name] for name in names if name]
        metrics = self._metrics(valid_points, labels, len(groups))
        metric_values = [metrics[key] for key in ("silhouette_score", "dbi", "z1")]
        if not valid_points:
            status = "tidak_tersedia"
            reason = "Tidak ada Petugas yang terisi pada titik berhasil geocoding."
        else:
            status = "tersedia" if all(value is not None for value in metric_values) else "sebagian"
            reason = metrics["alasan_na"]
        return {
            "jumlah_titik_geocoding": len(points),
            "jumlah_titik_evaluasi": len(valid_points),
            "jumlah_kurir_aktual": len(groups) or None,
            "silhouette_score": metrics["silhouette_score"],
            "dbi": metrics["dbi"],
            "z1": metrics["z1"],
            "status_evaluasi": status,
            "alasan_na": reason,
            "distribusi": [
                {"petugas": name, "jumlah_titik": distribution[name]}
                for name in sorted(distribution)
            ],
            "sidik_data": self.fingerprint(points),
        }

    def compare(self, points, km_labels, hb_labels, k):
        """
        Membandingkan hasil evaluasi K-Means dan HBCDP
        menggunakan titik pengiriman yang sama.

        Fungsi ini tidak menjalankan clustering ulang,
        tetapi hanya menghitung nilai evaluasi dari
        hasil pengelompokan yang sudah tersedia.

        Cluster yang tidak memiliki anggota tetap dihitung
        dalam evaluasi keseimbangan jumlah titik (Z1).

        Jika seluruh data tidak memiliki nama Petugas,
        evaluasi algoritma tetap menggunakan seluruh titik.

        Jika jumlah atau nomor cluster tidak sesuai,
        sistem akan menampilkan kesalahan.
        """
        if not isinstance(k, (int, np.integer)) or isinstance(k, bool) or k < 1:
            raise ValueError("K harus bilangan bulat positif.")
        assignments = []
        for labels in (km_labels, hb_labels):
            if len(labels) != len(points):
                raise ValueError("Jumlah label harus sama dengan jumlah titik geocoding.")
            if any(
                not isinstance(label, (int, np.integer))
                or isinstance(label, bool)
                or not 0 <= label < k
                for label in labels
            ):
                raise ValueError("Label cluster harus bilangan bulat pada rentang 0 sampai K-1.")
            assignments.append(labels)

        selected = [index for index, point in enumerate(points) if self._petugas(point)]
        scope = "petugas_valid" if selected else "seluruh_titik"
        if not selected:
            selected = list(range(len(points)))
        subset = [points[index] for index in selected]
        return {
            "kmeans": self._metrics(subset, [assignments[0][i] for i in selected], k),
            "hbcdp": self._metrics(subset, [assignments[1][i] for i in selected], k),
            "jumlah_titik_evaluasi": len(subset),
            "scope": scope,
        }
