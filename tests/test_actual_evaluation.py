"""Permanent unit coverage for actual assignments and fair metric comparison."""

from copy import deepcopy
import math
import unittest

from sklearn.metrics import davies_bouldin_score, silhouette_score

from services.actual_evaluation_service import ActualEvaluationService


def point(identifier, x, petugas=None, y=0):
    return {
        "id_pengiriman": identifier,
        "nosi": f"RESI{identifier:03d}",
        "petugas": petugas,
        "x_meter": x,
        "y_meter": y,
        "latitude": -7.98 + identifier / 10000,
        "longitude": 112.63 + identifier / 10000,
    }


class ActualEvaluationServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ActualEvaluationService()

    def test_missing_optional_petugas_is_unavailable_not_zero(self):
        missing_column = point(1, 0)
        del missing_column["petugas"]
        points = [missing_column, point(2, 1, None), point(3, 2, " \t ")]
        for rows in ([], points):
            with self.subTest(count=len(rows)):
                result = self.service.evaluate(rows)
                self.assertEqual(result["jumlah_titik_geocoding"], len(rows))
                self.assertEqual(result["jumlah_titik_evaluasi"], 0)
                self.assertIsNone(result["jumlah_kurir_aktual"])
                self.assertEqual(result["status_evaluasi"], "tidak_tersedia")
                self.assertTrue(result["alasan_na"])
                self.assertEqual(result["distribusi"], [])
                for metric in ("silhouette_score", "dbi", "z1"):
                    self.assertIsNone(result[metric])

    def test_petugas_whitespace_normalization_preserves_case(self):
        points = [
            point(1, 0, "  Adi  Setia  "),
            point(2, 1, "Adi\tSetia"),
            point(3, 10, "adi Setia"),
            point(4, 11, " \n "),
        ]
        result = self.service.evaluate(points)
        self.assertEqual(result["jumlah_titik_geocoding"], 4)
        self.assertEqual(result["jumlah_titik_evaluasi"], 3)
        self.assertEqual(result["jumlah_kurir_aktual"], 2)
        self.assertEqual(result["distribusi"], [
            {"petugas": "Adi Setia", "jumlah_titik": 2},
            {"petugas": "adi Setia", "jumlah_titik": 1},
        ])
        self.assertEqual(result["status_evaluasi"], "tersedia")
        self.assertIsNone(result["alasan_na"])

    def test_one_courier_has_zero_variance_but_na_geographic_metrics(self):
        result = self.service.evaluate([point(1, 0, "A"), point(2, 5, "A")])
        self.assertEqual(result["jumlah_kurir_aktual"], 1)
        self.assertEqual(result["z1"], 0.0)
        self.assertIsNone(result["silhouette_score"])
        self.assertIsNone(result["dbi"])
        self.assertEqual(result["status_evaluasi"], "sebagian")
        self.assertIn("kelompok=1", result["alasan_na"])

    def test_one_point_per_courier_has_na_geographic_metrics(self):
        result = self.service.evaluate([point(1, 0, "A"), point(2, 5, "B")])
        self.assertEqual(result["z1"], 0.0)
        self.assertIsNone(result["silhouette_score"])
        self.assertIsNone(result["dbi"])
        self.assertEqual(result["status_evaluasi"], "sebagian")
        self.assertTrue(result["alasan_na"])

    def test_actual_z1_is_population_variance_of_group_counts(self):
        points = [point(i + 1, i, "A") for i in range(4)]
        points.extend([point(5, 100, "B"), point(6, 200, "C")])
        result = self.service.evaluate(points)
        # Counts [4, 1, 1], mean 2: ((4-2)^2 + (1-2)^2 + (1-2)^2) / 3 = 2.
        self.assertEqual(result["z1"], 2.0)
        self.assertEqual(result["jumlah_kurir_aktual"], 3)
        self.assertEqual(result["status_evaluasi"], "tersedia")

    def test_metrics_use_projected_meters_not_latitude_longitude(self):
        points = [point(1, 0, "A"), point(2, 1, "A"), point(3, 10, "B"), point(4, 12, "B")]
        result = self.service.evaluate(points)
        coordinates = [[p["x_meter"], p["y_meter"]] for p in points]
        labels = [0, 0, 1, 1]
        self.assertAlmostEqual(result["silhouette_score"], silhouette_score(coordinates, labels))
        self.assertAlmostEqual(result["dbi"], davies_bouldin_score(coordinates, labels))

    def test_comparison_filters_existing_labels_and_retains_empty_clusters(self):
        points = [
            point(1, 0, "A"), point(2, 1, "A"),
            point(3, 10, "B"), point(4, 11, "B"),
            point(5, 1000, None), point(6, 2000, "  "),
        ]
        km_labels = [0, 0, 1, 1, 2, 2]
        hb_labels = [1, 1, 1, 0, 2, 2]
        result = self.service.compare(points, km_labels, hb_labels, 3)
        self.assertEqual(result["scope"], "petugas_valid")
        self.assertEqual(result["jumlah_titik_evaluasi"], 4)
        self.assertEqual(result["kmeans"]["cardinality"], [2, 2, 0])
        self.assertEqual(result["hbcdp"]["cardinality"], [1, 3, 0])
        self.assertAlmostEqual(result["kmeans"]["z1"], 8 / 9)
        self.assertAlmostEqual(result["hbcdp"]["z1"], 14 / 9)
        coordinates = [[p["x_meter"], p["y_meter"]] for p in points[:4]]
        for name, labels in (("kmeans", km_labels[:4]), ("hbcdp", hb_labels[:4])):
            self.assertAlmostEqual(result[name]["silhouette_score"], silhouette_score(coordinates, labels))
            self.assertAlmostEqual(result[name]["dbi"], davies_bouldin_score(coordinates, labels))
        self.assertEqual(km_labels, [0, 0, 1, 1, 2, 2])
        self.assertEqual(hb_labels, [1, 1, 1, 0, 2, 2])

    def test_comparison_uses_all_points_when_actual_assignments_absent(self):
        points = [point(1, 0), point(2, 1), point(3, 10), point(4, 11)]
        result = self.service.compare(points, [0, 0, 1, 1], [0, 1, 1, 1], 2)
        self.assertEqual(result["scope"], "seluruh_titik")
        self.assertEqual(result["jumlah_titik_evaluasi"], 4)
        self.assertEqual(result["kmeans"]["cardinality"], [2, 2])
        self.assertEqual(result["hbcdp"]["cardinality"], [1, 3])
        self.assertEqual(result["hbcdp"]["z1"], 1.0)

    def test_comparison_does_not_restore_groups_missing_from_fair_subset(self):
        points = [point(1, 0, "A"), point(2, 1, "A"), point(3, 10)]
        result = self.service.compare(points, [0, 0, 1], [1, 1, 0], 2)
        self.assertEqual(result["kmeans"]["cardinality"], [2, 0])
        self.assertEqual(result["kmeans"]["z1"], 1.0)
        self.assertIsNone(result["kmeans"]["silhouette_score"])
        self.assertIsNone(result["kmeans"]["dbi"])
        self.assertTrue(result["kmeans"]["alasan_na"])

    def test_fingerprint_is_order_independent_and_tracks_all_source_fields(self):
        points = [point(1, 0, "A"), point(2, 10, None)]
        fingerprint = self.service.fingerprint(points)
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(fingerprint, self.service.fingerprint(list(reversed(points))))
        changes = {
            "id_pengiriman": 99, "nosi": "OTHER", "petugas": "B",
            "x_meter": 99, "y_meter": 99, "latitude": -8, "longitude": 113,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = deepcopy(points)
                changed[1][field] = value
                self.assertNotEqual(fingerprint, self.service.fingerprint(changed))
        self.assertNotEqual(fingerprint, self.service.fingerprint(points[:1]))
        self.assertNotEqual(fingerprint, self.service.fingerprint(points + [points[1]]))
        edited_whitespace = deepcopy(points)
        edited_whitespace[0]["petugas"] = " A "
        self.assertNotEqual(fingerprint, self.service.fingerprint(edited_whitespace))

    def test_nonfinite_coordinates_yield_na_without_losing_count_variance(self):
        points = [point(1, math.nan, "A"), point(2, 1, "A"), point(3, 10, "B"), point(4, 11, "B")]
        result = self.service.evaluate(points)
        self.assertIsNone(result["silhouette_score"])
        self.assertIsNone(result["dbi"])
        self.assertEqual(result["z1"], 0.0)
        self.assertEqual(result["status_evaluasi"], "sebagian")
        self.assertTrue(result["alasan_na"])

    def test_coincident_centroids_are_na_dbi_not_fake_zero(self):
        points = [point(1, -1, "A"), point(2, 1, "A"), point(3, -2, "B"), point(4, 2, "B")]
        result = self.service.evaluate(points)
        self.assertIsNone(result["dbi"])
        self.assertIsNotNone(result["silhouette_score"])
        self.assertIn("centroid", result["alasan_na"])
        self.assertEqual(result["status_evaluasi"], "sebagian")


if __name__ == "__main__":
    unittest.main()
