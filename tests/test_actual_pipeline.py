"""Regresi baseline aktual sebelum clustering; memakai PostgreSQL uji terpisah."""
import csv
import io
import os
import unittest
import uuid

import psycopg2
from psycopg2 import sql

from app import app, geocoding_progress
from config import Config
from database.db import get_db_connection, get_actual_evaluation, query_db
from migrate import SCHEMA_FILE, run_sql_file


@unittest.skipUnless(os.getenv("GEOKURIR_INTEGRATION_TESTS") == "1", "Memerlukan PostgreSQL uji")
class ActualPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_name = Config.DB_NAME
        cls.test_name = f"geokurir_test_actual_{uuid.uuid4().hex[:10]}"
        cls.admin = psycopg2.connect(**Config.get_db_connection_params())
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.test_name)))
        Config.DB_NAME = cls.test_name

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.original_name
        try:
            with cls.admin.cursor() as cur:
                cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.test_name)))
        finally:
            cls.admin.close()

    def setUp(self):
        with get_db_connection() as conn:
            run_sql_file(conn, SCHEMA_FILE)
        geocoding_progress.clear()
        self.addCleanup(geocoding_progress.clear)
        self.client = app.test_client()

    def upload(self, with_petugas=True):
        stream = io.StringIO()
        writer = csv.writer(stream)
        headers = ["Nosi", "Tgl Antaran Pertama", "Alamat", "Kota"]
        writer.writerow(headers + (["Petugas (Kurir)"] if with_petugas else []))
        for index in range(8):
            row = [f"ACTUAL-{index}", "04/11/2026", f"Jl. Ijen No. {index + 1}", "Malang"]
            writer.writerow(row + (["  Kurir   A  " if index < 4 else "Kurir B" if index < 7 else ""] if with_petugas else []))
        response = self.client.post("/api/upload", data={
            "file": (io.BytesIO(stream.getvalue().encode()), "actual-test.csv")
        })
        self.assertEqual(response.status_code, 200, response.json)
        dataset_id = response.json["data"]["id_dataset"]
        # Fixture koordinat: isolasi alur aplikasi dari API Google, tanpa mengganti service.
        coordinates = [(0, 0), (1, 1), (2, 0), (0, 2), (100, 100), (101, 100), (100, 102), (250, 250)]
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id_pengiriman FROM data_pengiriman WHERE id_dataset=%s ORDER BY id_pengiriman", (dataset_id,))
                ids = [row[0] for row in cur.fetchall()]
                for point_id, (x, y) in zip(ids, coordinates):
                    cur.execute("""UPDATE data_pengiriman SET latitude=%s, longitude=%s,
                        x_meter=%s, y_meter=%s WHERE id_pengiriman=%s""",
                        (-7.9835954 + y / 111000, 112.6303597 + x / 111000, x, y, point_id))
        return dataset_id

    def geocode(self, dataset_id):
        response = self.client.post(f"/api/dataset/{dataset_id}/geocode", json={"limit": "all"})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["data"]["aktual"]

    def test_actual_persisted_before_clustering_and_reused_for_different_k(self):
        dataset_id = self.upload()
        self.assertIsNone(get_actual_evaluation(dataset_id))
        self.assertEqual(self.client.post(f"/api/cluster/{dataset_id}", json={"k": 3}).status_code, 409)
        actual = self.geocode(dataset_id)
        self.assertEqual(actual["jumlah_titik_geocoding"], 8)
        self.assertEqual(actual["jumlah_titik_evaluasi"], 7)
        self.assertEqual(actual["jumlah_kurir_aktual"], 2)
        self.assertEqual(actual["z1"], 0.25)
        self.assertEqual(query_db("SELECT COUNT(*) AS n FROM hasil_clustering", one=True)["n"], 0)
        self.assertEqual(get_actual_evaluation(dataset_id), actual)
        points = self.client.get(f"/api/dataset/{dataset_id}/points").json["data"]
        self.assertEqual(points[0]["petugas"], "Kurir A")
        self.assertIsNone(points[-1]["petugas"])
        for k in (3, 2):
            response = self.client.post(f"/api/cluster/{dataset_id}", json={"k": k, "limit": 3})
            self.assertEqual(response.status_code, 200, response.json)
            result = response.json["data"]
            self.assertEqual(result["n"], 8)
            self.assertEqual(result["perbandingan"]["jumlah_titik_evaluasi"], 7)
            self.assertEqual(result["perbandingan"]["scope"], "petugas_valid")
            self.assertEqual(len(result["perbandingan"]["kmeans"]["cardinality"]), k)
            self.assertEqual(sum(result["perbandingan"]["kmeans"]["cardinality"]), 7)
            self.assertEqual(get_actual_evaluation(dataset_id), actual)
            detail = self.client.get(f"/api/dataset/{dataset_id}").json["data"]
            self.assertEqual(detail["aktual"], actual)
            self.assertEqual(detail["perbandingan"], result["perbandingan"])
        exported = self.client.get(f"/api/download/export/{dataset_id}")
        rows = list(csv.DictReader(io.StringIO(exported.data.decode())))
        self.assertEqual(rows[0]["Petugas Aktual"], "Kurir A")
        self.assertEqual(rows[-1]["Petugas Aktual"], "")
        self.assertEqual(len(rows), 8)

    def test_missing_petugas_is_na_but_does_not_block_algorithms(self):
        dataset_id = self.upload(with_petugas=False)
        actual = self.geocode(dataset_id)
        self.assertEqual(actual["status_evaluasi"], "tidak_tersedia")
        self.assertEqual(actual["jumlah_titik_evaluasi"], 0)
        for field in ("jumlah_kurir_aktual", "silhouette_score", "dbi", "z1"):
            self.assertIsNone(actual[field], field)
        response = self.client.post(f"/api/cluster/{dataset_id}", json={"k": 2})
        self.assertEqual(response.status_code, 200, response.json)
        comparison = response.json["data"]["perbandingan"]
        self.assertEqual(comparison["scope"], "seluruh_titik")
        self.assertEqual(comparison["jumlah_titik_evaluasi"], 8)

    def test_petugas_edit_requires_refreshed_baseline(self):
        dataset_id = self.upload()
        before = self.geocode(dataset_id)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE data_pengiriman SET petugas='Kurir C' WHERE id_dataset=%s AND petugas IS NULL", (dataset_id,))
        detail = self.client.get(f"/api/dataset/{dataset_id}").json["data"]
        self.assertIsNone(detail["aktual"])
        response = self.client.post(f"/api/cluster/{dataset_id}", json={"k": 2})
        self.assertEqual(response.status_code, 409, response.json)
        refreshed = self.geocode(dataset_id)
        self.assertNotEqual(refreshed["sidik_data"], before["sidik_data"])
        self.assertEqual(refreshed["jumlah_kurir_aktual"], 3)
        self.assertEqual(refreshed["jumlah_titik_evaluasi"], 8)
        self.assertEqual(query_db("SELECT COUNT(*) AS n FROM evaluasi_aktual", one=True)["n"], 1)

    def test_dataset_delete_cascades_actual_baseline(self):
        dataset_id = self.upload()
        self.geocode(dataset_id)
        response = self.client.delete(f"/api/dataset/{dataset_id}")
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(get_actual_evaluation(dataset_id))

    def test_incremental_migration_preserves_rows_and_can_run_twice(self):
        from migrate import apply_pending_migrations, lock_migrations

        dataset_id = self.upload(with_petugas=False)
        before = query_db("""
            SELECT id_pengiriman, id_dataset, nosi, alamat_asli, latitude, longitude
            FROM data_pengiriman ORDER BY id_pengiriman
        """)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Hanya database sementara milik kelas ini: kembali ke skema lama.
                cur.execute("""
                    DROP TABLE evaluasi_aktual;
                    ALTER TABLE data_pengiriman DROP COLUMN petugas;
                    ALTER TABLE hasil_clustering DROP COLUMN evaluasi_perbandingan;
                """)
        for _ in range(2):
            with get_db_connection() as conn:
                lock_migrations(conn)
                apply_pending_migrations(conn)
        after = query_db("""
            SELECT id_pengiriman, id_dataset, nosi, alamat_asli, latitude, longitude
            FROM data_pengiriman ORDER BY id_pengiriman
        """)
        self.assertEqual(after, before)
        self.assertEqual(query_db("SELECT COUNT(*) AS n FROM schema_migrations", one=True)["n"], 1)
        self.assertTrue(all(row["petugas"] is None for row in query_db(
            "SELECT petugas FROM data_pengiriman WHERE id_dataset=%s", (dataset_id,)
        )))
        self.assertIsNone(get_actual_evaluation(dataset_id))


if __name__ == "__main__":
    unittest.main()
