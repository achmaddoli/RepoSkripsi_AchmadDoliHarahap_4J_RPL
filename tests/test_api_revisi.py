"""
Test integration untuk fitur revisi 29 Oktober:
- Format Tgl Antaran Pertama DD/MM/YYYY
- Response Preprocessing Service
- Unduhan template dengan format DD/MM/YYYY
"""

import io
import unittest
from app import app
from database.db import get_db_connection


class ApiRevisiTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_download_template_csv_contains_dd_mm_yyyy(self):
        """Memverifikasi template CSV menggunakan format 01/08/2025."""
        resp = self.client.get("/api/download/template/csv")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.decode("utf-8")
        self.assertIn("01/08/2025", data)
        self.assertNotIn("2025-08-01", data)

    def test_download_template_excel_status_ok(self):
        """Memverifikasi template Excel dapat diunduh tanpa error."""
        resp = self.client.get("/api/download/template/excel")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_upload_with_dd_mm_yyyy_and_preprocessing_breakdown(self):
        """Memverifikasi upload file CSV dengan tanggal DD/MM/YYYY dan rincian preprocessing."""
        csv_content = (
            "No.,Nosi,Tgl Antaran Pertama,Alamat,Kota\n"
            "1,RESI001,01/08/2025,JL. Ijen NO 1,Malang\n"
            "2,,01/08/2025,Jl. Ijen No. 2,Malang\n"  # Kosong resi
            "3,RESI003,01/08/2025,Jl. Pemuda No. 3,Surabaya\n"  # Luar Malang
            "4,RESI001,01/08/2025,Jl. Ijen No. 1,Malang\n"  # Duplikat
            "5,RESI005,01/08/2025,GG. Kelinci NO. 5,Malang\n"  # Valid 2
        )

        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "test_revisi_upload.csv")
        }

        resp = self.client.post(
            "/api/upload",
            data=data,
            content_type="multipart/form-data"
        )

        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data["success"])
        res_data = json_data["data"]

        # Format tanggal display
        self.assertEqual(res_data["tanggal_data"], "01/08/2025")

        # Rincian preprocessing
        self.assertEqual(res_data["total_awal"], 5)
        self.assertEqual(res_data["total_valid"], 2)
        self.assertEqual(res_data["total_eliminasi"], 3)

        prep = res_data["preprocessing"]
        self.assertEqual(prep["rincian"]["data_kosong"]["count"], 1)
        self.assertEqual(prep["rincian"]["di_luar_wilayah"]["count"], 1)
        self.assertEqual(prep["rincian"]["resi_duplikat"]["count"], 1)
        self.assertEqual(prep["rincian"]["normalisasi"]["count"], 2)

        # Cleanup test dataset from DB
        ds_id = res_data.get("id_dataset")
        if ds_id:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM dataset WHERE id_dataset = %s;", (ds_id,))

    def test_compute_shapely_hull_latlng(self):
        """Memverifikasi pembentukan geometri convex hull berbasis Shapely untuk Leaflet."""
        from app import compute_shapely_hull_latlng

        # 0 titik
        self.assertEqual(compute_shapely_hull_latlng([]), [])

        # 1 titik
        p1 = [(-7.982, 112.630)]
        self.assertEqual(compute_shapely_hull_latlng(p1), [[-7.982, 112.630]])

        # 2 titik
        p2 = [(-7.982, 112.630), (-7.985, 112.635)]
        hull_p2 = compute_shapely_hull_latlng(p2)
        self.assertEqual(len(hull_p2), 2)

        # 3+ titik non-kolinear (harus tertutup: titik awal == titik akhir)
        p3 = [
            (-7.980, 112.630),
            (-7.985, 112.630),
            (-7.985, 112.635),
            (-7.982, 112.632)  # titik di dalam
        ]
        hull_p3 = compute_shapely_hull_latlng(p3)
        self.assertTrue(len(hull_p3) >= 4)
        self.assertEqual(hull_p3[0], hull_p3[-1])  # closed ring


if __name__ == "__main__":
    unittest.main()
