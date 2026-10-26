import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import get_db_connection

def seed_dataset1():
    with get_db_connection() as conn:
        cur = conn.cursor()

        # 1. Pastikan id_clustering = 2 ada di hasil_clustering
        cur.execute("""
            SELECT id_clustering FROM hasil_clustering WHERE id_dataset = 1 ORDER BY id_clustering DESC LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            cur.execute("""
                INSERT INTO hasil_clustering (id_dataset, jumlah_cluster, silhouette_score, dbi)
                VALUES (1, 5, 0.4421, 0.6213) RETURNING id_clustering;
            """)
            id_clustering = cur.fetchone()[0]
        else:
            id_clustering = row[0]

        # Bersihkan cluster lama jika ada
        cur.execute("DELETE FROM cluster WHERE id_clustering = %s;", (id_clustering,))

        # 2. Insert 5 Cluster K-Means untuk dataset 1
        clusters_info = [
            (1, 2400.5, 350.2, 1845),
            (2, -1650.3, -420.5, 2120),
            (3, -520.1, 2310.8, 1450),
            (4, 110.4, -480.2, 2300),
            (5, 3100.8, 3200.4, 900)
        ]
        cluster_id_map = {}
        for num, cx, cy, cnt in clusters_info:
            cur.execute("""
                INSERT INTO cluster (id_clustering, nomor_cluster, centroid_x, centroid_y, jumlah_anggota)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_cluster;
            """, (id_clustering, num, cx, cy, cnt))
            cluster_id_map[num] = cur.fetchone()[0]

        # 3. Update / Insert hasil_optimasi
        steps_data = [
            {"step": "Step 1", "nama": "Direct Reassignment", "cardinality": "[1720, 1726, 1721, 1724, 1724]", "z1": "4.80", "z2": "16.340,50 m", "reassigned": 580},
            {"step": "Step 2", "nama": "Path Reassignment (BFS)", "cardinality": "[1720, 1726, 1721, 1724, 1724]", "z1": "4.80", "z2": "16.340,50 m", "reassigned": 0},
            {"step": "Step 3", "nama": "Pairwise Exchange", "cardinality": "[1722, 1725, 1722, 1723, 1723]", "z1": "1.60", "z2": "15.120,20 m", "reassigned": 12},
            {"step": "Step 4", "nama": "Multiple Exchange (Bellman-Ford)", "cardinality": "[1723, 1725, 1722, 1723, 1722]", "z1": "1.20", "z2": "14.250,80 m", "reassigned": 8}
        ]
        cur.execute("SELECT id_optimasi FROM hasil_optimasi WHERE id_clustering = %s;", (id_clustering,))
        ho_row = cur.fetchone()
        if not ho_row:
            cur.execute("""
                INSERT INTO hasil_optimasi (id_clustering, nilai_z1, nilai_z2, silhouette_score, dbi, steps_json, status)
                VALUES (%s, 1.20, 14250.80, 0.215, 1.185, %s, 'SUCCESS') RETURNING id_optimasi;
            """, (id_clustering, json.dumps(steps_data)))
            id_optimasi = cur.fetchone()[0]
        else:
            id_optimasi = ho_row[0]
            cur.execute("""
                UPDATE hasil_optimasi 
                SET nilai_z1 = 1.20, nilai_z2 = 14250.80, silhouette_score = 0.215, dbi = 1.185, steps_json = %s, status = 'SUCCESS'
                WHERE id_optimasi = %s;
            """, (json.dumps(steps_data), id_optimasi))

        # 4. Insert 5 Zona Kurir
        cur.execute("DELETE FROM zona_kurir WHERE id_optimasi = %s;", (id_optimasi,))
        zonas_info = [
            (1, 1723, json.dumps({"type": "Polygon", "coordinates": [[[112.633937,-7.986127],[112.650106,-7.990748],[112.654598,-7.977244],[112.633937,-7.986127]]]})),
            (2, 1725, json.dumps({"type": "Polygon", "coordinates": [[[112.610153,-7.986014],[112.612412,-7.997633],[112.613853,-7.984231],[112.620077,-7.979206],[112.610153,-7.986014]]]})),
            (3, 1722, json.dumps({"type": "Polygon", "coordinates": [[[112.619265,-7.954532],[112.625892,-7.957535],[112.627063,-7.971297],[112.629402,-7.978406],[112.619265,-7.954532]]]})),
            (4, 1723, json.dumps({"type": "Polygon", "coordinates": [[[112.627714,-7.982693],[112.628024,-7.990477],[112.630092,-8.005489],[112.634098,-7.983912],[112.627714,-7.982693]]]})),
            (5, 1722, json.dumps({"type": "Polygon", "coordinates": [[[112.632696,-7.963284],[112.636022,-7.982264],[112.660160,-7.953797],[112.661797,-7.975192],[112.632696,-7.963284]]]}))
        ]
        for num, cnt, poly in zonas_info:
            cur.execute("""
                INSERT INTO zona_kurir (id_optimasi, nomor_zona, jumlah_anggota, polygon)
                VALUES (%s, %s, %s, %s);
            """, (id_optimasi, num, cnt, poly))

        # 5. Baca sample points dari js/data.js batch_8615
        data_js_path = os.path.join(BASE_DIR, "js", "data.js")
        with open(data_js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        start_str = "'batch_8615': {"
        points_str = "points: ["
        idx_start = js_content.find(start_str)
        if idx_start != -1:
            idx_pts = js_content.find(points_str, idx_start)
            if idx_pts != -1:
                idx_pts_start = js_content.find("[", idx_pts)
                idx_pts_end = js_content.find("]\n  },", idx_pts_start)
                if idx_pts_end == -1:
                    idx_pts_end = js_content.find("]", idx_pts_start)
                raw_json = js_content[idx_pts_start:idx_pts_end+1]
                try:
                    points_list = json.loads(raw_json)
                except Exception as e:
                    print("Failed to parse json points:", e)
                    points_list = []
            else:
                points_list = []
        else:
            points_list = []

        print(f"Loaded {len(points_list)} sample points for batch_8615")

        # Bersihkan data_pengiriman lama untuk dataset 1
        cur.execute("DELETE FROM data_pengiriman WHERE id_dataset = 1;")

        # Insert sample points
        for pt in points_list:
            alamat = pt.get("alamat", "Malang")
            lat = pt.get("lat", -7.9835954)
            lng = pt.get("lng", 112.6303597)
            c_init = pt.get("c_init", 1)
            c_final = pt.get("c_final", 1)

            kcu_lat = -7.9835954
            kcu_lng = 112.6303597
            dy = (lat - kcu_lat) * 111320.0
            dx = (lng - kcu_lng) * 111320.0 * 0.99047

            cur.execute("""
                INSERT INTO data_pengiriman (id_dataset, alamat_asli, alamat_bersih, latitude, longitude, x_meter, y_meter, status_geocoding)
                VALUES (1, %s, %s, %s, %s, %s, %s, 'SUCCESS') RETURNING id_pengiriman;
            """, (alamat, alamat, lat, lng, dx, dy))
            id_pengiriman = cur.fetchone()[0]

            target_cluster_id = cluster_id_map.get(c_init, list(cluster_id_map.values())[0])
            cur.execute("""
                INSERT INTO anggota_cluster (id_cluster, id_pengiriman, jarak_ke_centroid, nomor_zona)
                VALUES (%s, %s, %s, %s);
            """, (target_cluster_id, id_pengiriman, 500.0, c_final))

    print("Dataset 1 seeding completed successfully!")

if __name__ == "__main__":
    seed_dataset1()
