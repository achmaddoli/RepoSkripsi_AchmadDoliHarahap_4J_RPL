"""Uji PostgreSQL terisolasi: GEOKURIR_INTEGRATION_TESTS=1 python -m unittest discover -s tests."""
import os
import unittest
import uuid

import psycopg2
from psycopg2 import sql

from app import app, geocoding_progress
from config import Config
from database.db import get_db_connection
from migrate import SCHEMA_FILE, run_sql_file


@unittest.skipUnless(os.getenv('GEOKURIR_INTEGRATION_TESTS') == '1', 'Memerlukan PostgreSQL untuk database uji sementara')
class DatasetDeleteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_name = Config.DB_NAME
        cls.test_name = f'geokurir_test_delete_{uuid.uuid4().hex[:10]}'
        cls.admin = psycopg2.connect(**Config.get_db_connection_params())
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.test_name)))
        Config.DB_NAME = cls.test_name

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.original_name
        try:
            with cls.admin.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(cls.test_name)))
        finally:
            cls.admin.close()

    def setUp(self):
        with get_db_connection() as conn:
            run_sql_file(conn, SCHEMA_FILE)
        self.client = app.test_client()
        self.target = self.create_dataset('delete-me.csv')
        self.other = self.create_dataset('keep-me.csv')

    def create_dataset(self, name, processed=True):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO dataset(nama_file,tanggal_data,jumlah_data,status)
                    VALUES (%s,'2026-10-25',1,%s) RETURNING id_dataset""",
                            (name, 'COMPLETED' if processed else 'UPLOADED'))
                dataset_id = cur.fetchone()[0]
                cur.execute("""INSERT INTO data_pengiriman(id_dataset,alamat_asli,nosi)
                    VALUES (%s,'Jl. Uji No. 1','TEST') RETURNING id_pengiriman""", (dataset_id,))
                pengiriman_id = cur.fetchone()[0]
                if processed:
                    cur.execute('INSERT INTO hasil_clustering(id_dataset,jumlah_cluster) VALUES (%s,2) RETURNING id_clustering', (dataset_id,))
                    clustering_id = cur.fetchone()[0]
                    cur.execute('INSERT INTO cluster(id_clustering,nomor_cluster,jumlah_anggota) VALUES (%s,1,1) RETURNING id_cluster', (clustering_id,))
                    cluster_id = cur.fetchone()[0]
                    cur.execute('INSERT INTO anggota_cluster(id_cluster,id_pengiriman,nomor_zona) VALUES (%s,%s,1)', (cluster_id, pengiriman_id))
                    cur.execute('INSERT INTO hasil_optimasi(id_clustering) VALUES (%s) RETURNING id_optimasi', (clustering_id,))
                    optimasi_id = cur.fetchone()[0]
                    cur.execute("INSERT INTO zona_kurir(id_optimasi,nomor_zona,jumlah_anggota,polygon) VALUES (%s,1,1,'{}')", (optimasi_id,))
                    # Riwayat dapat hanya menunjuk salah satu level relasi.
                    cur.execute("INSERT INTO history_proses(id_clustering,jenis_proses,status) VALUES (%s,'KMEANS_CLUSTERING','COMPLETED')", (clustering_id,))
                    cur.execute("INSERT INTO history_proses(id_optimasi,jenis_proses,status) VALUES (%s,'HBCDP_OPTIMIZATION','COMPLETED')", (optimasi_id,))
                cur.execute("INSERT INTO history_proses(id_dataset,jenis_proses,status) VALUES (%s,'UPLOAD','COMPLETED')", (dataset_id,))
                return dataset_id

    def snapshot(self):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                result = {}
                for table in ('dataset', 'data_pengiriman', 'hasil_clustering', 'cluster',
                              'anggota_cluster', 'hasil_optimasi', 'zona_kurir', 'history_proses'):
                    cur.execute(sql.SQL('SELECT * FROM {} ORDER BY 1').format(sql.Identifier(table)))
                    result[table] = cur.fetchall()
                return result

    def test_delete_cascades_and_preserves_other_dataset(self):
        before = self.snapshot()
        geocoding_progress[self.target] = {'status': 'COMPLETED'}
        response = self.client.delete(f'/api/dataset/{self.target}')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['success'])
        self.assertNotIn(self.target, geocoding_progress)
        after = self.snapshot()
        for table in before:
            expected_remaining = 3 if table == 'history_proses' else 1
            self.assertEqual(len(after[table]), expected_remaining, table)
            self.assertEqual(after[table], before[table][-expected_remaining:], table)
        self.assertEqual(self.client.get(f'/api/dataset/{self.target}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/dataset/{self.other}').status_code, 200)
        self.assertEqual([d['id_dataset'] for d in self.client.get('/api/datasets').json['data']], [self.other])
        self.assertEqual(self.client.delete(f'/api/dataset/{self.target}').status_code, 404)
        self.assertEqual(self.snapshot(), after)

    def test_unprocessed_dataset_is_deleted_with_points_and_history(self):
        before = self.snapshot()
        unprocessed = self.create_dataset('not-processed.csv', processed=False)
        response = self.client.delete(f'/api/dataset/{unprocessed}')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['success'])
        self.assertEqual(self.client.get(f'/api/dataset/{unprocessed}').status_code, 404)
        self.assertEqual(self.snapshot(), before)

    def test_missing_dataset_does_not_change_data(self):
        before = self.snapshot()
        self.assertEqual(self.client.delete('/api/dataset/999999').status_code, 404)
        self.assertEqual(self.snapshot(), before)

    def test_bulk_delete_cascades_and_preserves_unselected_dataset(self):
        second_target = self.create_dataset('also-delete-me.csv')
        before = self.snapshot()
        for dataset_id in (self.target, self.other, second_target):
            geocoding_progress[dataset_id] = {'status': 'COMPLETED'}
        self.addCleanup(geocoding_progress.clear)
        response = self.client.delete('/api/datasets', json={
            'ids': [second_target, self.target, self.target]
        })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data'], {
            'ids': [self.target, second_target], 'deleted_count': 2
        })
        after = self.snapshot()
        for table in before:
            expected = before[table][3:6] if table == 'history_proses' else before[table][1:2]
            self.assertEqual(after[table], expected, table)
        self.assertEqual(set(geocoding_progress), {self.other})
        self.assertEqual([d['id_dataset'] for d in self.client.get('/api/datasets').json['data']], [self.other])
        self.assertEqual(self.client.get(f'/api/dataset/{self.other}').status_code, 200)

    def test_bulk_invalid_ids_do_not_change_data(self):
        before = self.snapshot()
        for payload in (None, [], {}, {'ids': []}, {'ids': '1,2'},
                        {'ids': [True]}, {'ids': ['1']}, {'ids': [1.5]},
                        {'ids': [0]}, {'ids': [-1]}, {'ids': [None]}):
            with self.subTest(payload=payload):
                response = self.client.delete('/api/datasets', json=payload)
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.snapshot(), before)

    def test_bulk_missing_dataset_rejects_whole_selection(self):
        before = self.snapshot()
        response = self.client.delete('/api/datasets', json={'ids': [self.target, 999999]})
        self.assertEqual(response.status_code, 404, response.json)
        self.assertEqual(self.snapshot(), before)

    def test_bulk_deletes_processed_and_unprocessed_datasets_together(self):
        before = self.snapshot()
        unprocessed = self.create_dataset('not-processed.csv', processed=False)
        response = self.client.delete('/api/datasets', json={'ids': [self.target, unprocessed]})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['deleted_count'], 2)
        after = self.snapshot()
        for table in before:
            expected_remaining = 3 if table == 'history_proses' else 1
            self.assertEqual(after[table], before[table][-expected_remaining:], table)
        self.assertEqual([d['id_dataset'] for d in self.client.get('/api/datasets').json['data']], [self.other])

    def test_bulk_database_error_rolls_back_all_selected_datasets(self):
        before = self.snapshot()
        geocoding_progress[self.target] = {'status': 'COMPLETED'}
        self.addCleanup(geocoding_progress.clear)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE FUNCTION reject_bulk_delete() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        IF OLD.nama_file = 'keep-me.csv' THEN
                            RAISE EXCEPTION 'Simulated bulk delete failure';
                        END IF;
                        RETURN OLD;
                    END $$;
                    CREATE TRIGGER reject_bulk_delete BEFORE DELETE ON dataset
                    FOR EACH ROW EXECUTE FUNCTION reject_bulk_delete();""")
        response = self.client.delete('/api/datasets', json={'ids': [self.target, self.other]})
        self.assertEqual(response.status_code, 500, response.json)
        self.assertEqual(self.snapshot(), before)
        self.assertIn(self.target, geocoding_progress)

    def test_database_error_rolls_back_history_and_results(self):
        before = self.snapshot()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE FUNCTION reject_delete() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'Simulated delete failure'; END $$;
                    CREATE TRIGGER reject_delete BEFORE DELETE ON dataset
                    FOR EACH ROW EXECUTE FUNCTION reject_delete();""")
        response = self.client.delete(f'/api/dataset/{self.target}')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json['success'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
