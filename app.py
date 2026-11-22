import os
import io
import csv
import json
import re
import time
from datetime import datetime
from uuid import UUID
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from werkzeug.utils import secure_filename
from shapely.geometry import MultiPoint
import xlsxwriter

from config import Config
from database.db import (
    query_db, execute_db, execute_upload_transaction, get_db_connection,
    get_actual_evaluation, save_actual_evaluation,
)
from services.geocoding_service import GeocodingService
from services.kmeans_service import KMeansService
from services.hbcdp_service import HBCDPService
from services.preprocessing_service import preprocessing_service
from services.actual_evaluation_service import ActualEvaluationService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Hanya direktori publik yang dilayani; folder proyek berisi SQL dan konfigurasi.
app = Flask(
    __name__,
    static_folder=None,
    template_folder=os.path.join(BASE_DIR, "templates")
)
app.config.from_object(Config)

# Inisialisasi Service Classes sesuai Class Diagram
geocoding_service = GeocodingService(api_key=Config.GOOGLE_MAPS_API_KEY)
kmeans_service = KMeansService()
hbcdp_service = HBCDPService()
actual_evaluation_service = ActualEvaluationService()


def successful_dataset_points(id_dataset):
    """Seluruh titik hasil geocoding; satu sumber data untuk baseline dan algoritma."""
    return query_db("""
        SELECT id_pengiriman, nosi, petugas, alamat_bersih, alamat_asli,
               latitude, longitude, x_meter, y_meter, status_geocoding
        FROM data_pengiriman
        WHERE id_dataset = %s AND status_geocoding = 'SUCCESS'
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND x_meter IS NOT NULL AND y_meter IS NOT NULL
        ORDER BY id_pengiriman;
    """, (id_dataset,))

def compute_shapely_hull_latlng(points_latlng):
    """
    Menghitung Convex Hull menggunakan Shapely dari sekumpulan koordinat (lat, lng).
    Mengembalikan array koordinat [[lat, lng], ...] yang siap langsung dirender oleh Leaflet.
    - 0 titik: []
    - 1 titik: [[lat, lng]]
    - 2 titik / kolinear: [[lat1, lng1], [lat2, lng2]]
    - >= 3 titik planar: [[lat1, lng1], [lat2, lng2], ..., [lat1, lng1]] (closed ring)
    """
    pts = [
        (float(p[0]), float(p[1]))
        for p in points_latlng
        if p is not None and p[0] is not None and p[1] is not None
    ]
    if not pts:
        return []

    unique_pts = list(dict.fromkeys(pts))
    if len(unique_pts) == 1:
        return [[unique_pts[0][0], unique_pts[0][1]]]
    if len(unique_pts) == 2:
        return [[unique_pts[0][0], unique_pts[0][1]], [unique_pts[1][0], unique_pts[1][1]]]

    try:
        geom = MultiPoint(unique_pts).convex_hull
        if geom.geom_type == "Polygon":
            return [[float(lat), float(lng)] for lat, lng in geom.exterior.coords]
        elif geom.geom_type == "LineString":
            return [[float(lat), float(lng)] for lat, lng in geom.coords]
        elif geom.geom_type == "Point":
            return [[float(geom.x), float(geom.y)]]
    except Exception:
        pass
    return [[p[0], p[1]] for p in unique_pts]

# Penyimpanan sementara progres geocoding per dataset
from threading import Lock

geocoding_progress = {}
geocoding_progress_lock = Lock()

# Progress upload hanya disimpan di proses Flask ini (single worker).
preprocessing_progress = {}
preprocessing_progress_lock = Lock()


def set_preprocessing_progress(upload_id, **fields):
    if not upload_id:
        return
    with preprocessing_progress_lock:
        if upload_id in preprocessing_progress:
            preprocessing_progress[upload_id].update(fields)


# ============================================================================
# 1. Halaman Web (Frontend Routes)
# ============================================================================

@app.route("/<any(css,js,assets):directory>/<path:filename>")
def public_asset(directory, filename):
    return send_from_directory(os.path.join(BASE_DIR, directory), filename)


@app.route("/")
@app.route("/index.html")
def index():
    """Menampilkan halaman utama SPA GeoKurir Malang."""
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard_view():
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)

@app.route("/upload")
@app.route("/upload.html")
def upload_view():
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)

@app.route("/zona")
@app.route("/zona.html")
def zona_view():
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)

@app.route("/evaluasi")
@app.route("/evaluasi.html")
def evaluasi_view():
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)


@app.route("/hapus-dataset")
@app.route("/hapus-dataset.html")
def hapus_dataset_view():
    return render_template("index.html", google_maps_api_key=Config.GOOGLE_MAPS_API_KEY)


# ============================================================================
# 2. REST API: Konfigurasi & Geocoding
# ============================================================================

@app.route("/api/config", methods=["GET"])
def get_app_config():
    """Mengambil konfigurasi client termasuk Google Maps API Key, batas geocoding dari .env, dan origin KCU Malang."""
    return jsonify({
        "success": True,
        "google_maps_api_key": Config.GOOGLE_MAPS_API_KEY,
        "has_google_maps_key": bool(Config.GOOGLE_MAPS_API_KEY),
        "geocoding_limit": Config.GEOCODING_LIMIT,
        "kcu_origin": {
            "lat": Config.KCU_ORIGIN_LAT,
            "lng": Config.KCU_ORIGIN_LON,
            "name": Config.KCU_NAME
        }
    })


@app.route("/api/geocode", methods=["GET", "POST"])
def geocode_address():
    """
    Melakukan geocoding alamat menggunakan Google Maps Geocoding API
    (atau fallback deterministic lookup Kota Malang jika API key belum diisi).
    """
    try:
        address = ""
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            address = data.get("address", "")
        if not address:
            address = request.args.get("address", "")

        if not address:
            return jsonify({"success": False, "error": "Parameter 'address' wajib disertakan"}), 400

        result = geocoding_service.geocode(address)
        
        return jsonify({
            "success": result["status"] == "SUCCESS",
            "data": result,
            "error": result.get("error"),
            "used_google_api": bool(Config.GOOGLE_MAPS_API_KEY)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 2. REST API: Datasets & Informasi Clustering
# ============================================================================

@app.route("/api/datasets", methods=["GET"])
def get_datasets():
    """Mengambil daftar seluruh dataset yang tersimpan di database beserta informasi titik yang diproses dan timestamp."""
    try:
        sql = """
            SELECT 
                d.id_dataset,
                d.nama_file,
                d.tanggal_data::text,
                d.jumlah_data,
                d.jumlah_kurir,
                d.status,
                d.created_at::text AS waktu_upload,
                latest_hc.waktu_proses::text AS waktu_proses,
                COALESCE(latest_hc.titik_diproses, 0) AS titik_diproses
            FROM dataset d
            LEFT JOIN (
                SELECT 
                    hc.id_dataset,
                    hc.created_at AS waktu_proses,
                    COALESCE(SUM(c.jumlah_anggota), 0) AS titik_diproses
                FROM (
                    SELECT DISTINCT ON (id_dataset) id_clustering, id_dataset, created_at
                    FROM hasil_clustering
                    ORDER BY id_dataset, id_clustering DESC
                ) hc
                LEFT JOIN cluster c ON hc.id_clustering = c.id_clustering
                GROUP BY hc.id_dataset, hc.id_clustering, hc.created_at
            ) latest_hc ON d.id_dataset = latest_hc.id_dataset
            ORDER BY d.id_dataset DESC;
        """
        datasets = query_db(sql)
        return jsonify({"success": True, "data": datasets})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/<int:id_dataset>", methods=["DELETE"])
@app.route("/api/datasets", methods=["DELETE"])
def delete_dataset(id_dataset=None):
    """Hapus satu atau beberapa dataset beserta hasil prosesnya secara atomik."""
    single = id_dataset is not None
    if single:
        dataset_ids = [id_dataset]
    else:
        payload = request.get_json(silent=True)
        dataset_ids = payload.get("ids") if isinstance(payload, dict) else None
        if (not isinstance(dataset_ids, list) or not dataset_ids
                or any(type(value) is not int or value <= 0 for value in dataset_ids)):
            return jsonify({
                "success": False,
                "error": "Pilih minimal satu dataset dengan ID berupa bilangan bulat positif."
            }), 400
        dataset_ids = sorted(set(dataset_ids))

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT d.id_dataset
                    FROM dataset d WHERE d.id_dataset = ANY(%s)
                    ORDER BY d.id_dataset FOR UPDATE;
                """, (dataset_ids,))
                datasets = cur.fetchall()
                if len(datasets) != len(dataset_ids):
                    return jsonify({
                        "success": False,
                        "error": "Dataset tidak ditemukan. Muat ulang daftar dataset sebelum mencoba kembali."
                    }), 404
                # Hapus log sebelum CASCADE mengosongkan referensinya (SET NULL).
                cur.execute("""
                    DELETE FROM history_proses
                    WHERE id_dataset = ANY(%s)
                       OR id_clustering IN (
                           SELECT id_clustering FROM hasil_clustering WHERE id_dataset = ANY(%s)
                       )
                       OR id_optimasi IN (
                           SELECT ho.id_optimasi FROM hasil_optimasi ho
                           JOIN hasil_clustering hc ON hc.id_clustering = ho.id_clustering
                           WHERE hc.id_dataset = ANY(%s)
                       );
                """, (dataset_ids, dataset_ids, dataset_ids))
                # FK ON DELETE CASCADE membersihkan titik, cluster, anggota,
                # hasil optimasi, serta zona dalam transaksi yang sama.
                cur.execute("DELETE FROM dataset WHERE id_dataset = ANY(%s);", (dataset_ids,))

        with geocoding_progress_lock:
            for deleted_id in dataset_ids:
                geocoding_progress.pop(deleted_id, None)
        result = {"ids": dataset_ids, "deleted_count": len(dataset_ids)}
        if single:
            result["id_dataset"] = id_dataset
        return jsonify({
            "success": True,
            "message": f"{len(dataset_ids)} dataset beserta seluruh hasil proses dan riwayatnya berhasil dihapus.",
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/<int:id_dataset>", methods=["GET"])
def get_dataset_detail(id_dataset):
    """
    Mengambil data lengkap sebuah dataset termasuk hasil evaluasi K-Means dan HBCDP.
    """
    try:
        # 1. Ambil data dataset
        ds_sql = """
            SELECT id_dataset, nama_file, tanggal_data::text, jumlah_data, jumlah_kurir, status,
                   total_awal, eliminasi_wilayah, eliminasi_kosong, eliminasi_duplikat,
                   eliminasi_alamat_umum, total_eliminasi, preprocessing_json
            FROM dataset WHERE id_dataset = %s;
        """
        ds = query_db(ds_sql, (id_dataset,), one=True)
        if not ds:
            return jsonify({"success": False, "error": "Dataset tidak ditemukan"}), 404

        # Format tanggal DD/MM/YYYY
        if ds.get("tanggal_data"):
            try:
                ds["tanggal_data_formatted"] = datetime.strptime(
                    str(ds["tanggal_data"]), "%Y-%m-%d"
                ).strftime("%d/%m/%Y")
            except Exception:
                ds["tanggal_data_formatted"] = str(ds["tanggal_data"])
        else:
            ds["tanggal_data_formatted"] = "-"

        # Parse preprocessing JSON jika ada
        if ds.get("preprocessing_json"):
            try:
                ds["preprocessing"] = json.loads(ds["preprocessing_json"])
            except Exception:
                ds["preprocessing"] = None
        else:
            ds["preprocessing"] = None

        # 2. Ambil data hasil clustering awal (sesi terbaru)
        hc_sql = """
            SELECT id_clustering, jumlah_cluster, silhouette_score, dbi,
                   waktu_komputasi, created_at::text, evaluasi_perbandingan
            FROM hasil_clustering
            WHERE id_dataset = %s
            ORDER BY id_clustering DESC LIMIT 1;
        """
        hc = query_db(hc_sql, (id_dataset,), one=True)
        if hc and hc.get("waktu_komputasi") is not None:
            wk = float(hc["waktu_komputasi"])
            hc["waktu_komputasi_str"] = f"{wk:.2f}".replace(".", ",") + " detik"
        elif hc:
            hc["waktu_komputasi_str"] = "-"

        # 3. Ambil data cluster K-Means awal
        clusters_kmeans = []
        if hc:
            cl_sql = """
                SELECT id_cluster, nomor_cluster, centroid_x, centroid_y, jumlah_anggota
                FROM cluster
                WHERE id_clustering = %s
                ORDER BY nomor_cluster ASC;
            """
            clusters_kmeans = query_db(cl_sql, (hc["id_clustering"],))

            # Hitung Z1 variansi K-Means jika ada cluster
            if clusters_kmeans:
                k_val = len(clusters_kmeans)
                tot = sum(c["jumlah_anggota"] for c in clusters_kmeans)
                y_bar = tot / k_val if k_val > 0 else 0
                hc["z1"] = round(sum((c["jumlah_anggota"] - y_bar) ** 2 for c in clusters_kmeans) / k_val, 2)
            else:
                hc["z1"] = 0.0

        # 4. Ambil data hasil optimasi HBCDP
        ho = None
        zonas_hbcdp = []
        if hc:
            ho_sql = """
                SELECT id_optimasi, nilai_z1, nilai_z2, silhouette_score, dbi, steps_json, status, created_at::text
                FROM hasil_optimasi
                WHERE id_clustering = %s;
            """
            ho = query_db(ho_sql, (hc["id_clustering"],), one=True)

            if ho:
                # Parse steps_json jika tersimpan
                if ho.get("steps_json"):
                    try:
                        ho["steps"] = json.loads(ho["steps_json"])
                    except Exception:
                        ho["steps"] = []
                else:
                    ho["steps"] = []

                zk_sql = """
                    SELECT id_zona, nomor_zona, jumlah_anggota, polygon
                    FROM zona_kurir
                    WHERE id_optimasi = %s
                    ORDER BY nomor_zona ASC;
                """
                zonas_hbcdp = query_db(zk_sql, (ho["id_optimasi"],))
        # Ambil ringkasan status geocoding dan daftar geocoding gagal
        geo_counts_sql = """
            SELECT 
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status_geocoding = 'SUCCESS') AS berhasil,
                COUNT(*) FILTER (WHERE status_geocoding = 'FAILED') AS gagal,
                COUNT(*) FILTER (WHERE status_geocoding = 'PENDING') AS pending
            FROM data_pengiriman
            WHERE id_dataset = %s;
        """
        geo_counts = query_db(geo_counts_sql, (id_dataset,), one=True) or {
            "total": 0, "berhasil": 0, "gagal": 0, "pending": 0
        }

        gagal_sql = """
            SELECT id_pengiriman, nosi, petugas, alamat_asli, alamat_bersih, keterangan_geocoding
            FROM data_pengiriman
            WHERE id_dataset = %s AND status_geocoding = 'FAILED'
            ORDER BY id_pengiriman ASC;
        """
        gagal_rows = query_db(gagal_sql, (id_dataset,)) or []
        gagal_items = [
            {
                "no": idx + 1,
                "resi": r["nosi"] or "-",
                "petugas": r["petugas"] or "-",
                "alamat": r["alamat_bersih"] or r["alamat_asli"] or "-",
                "keterangan": r["keterangan_geocoding"] or "Lokasi tidak ditemukan"
            }
            for idx, r in enumerate(gagal_rows)
        ]

        # Deteksi keberadaan kolom Petugas dari metadata preprocessing
        prep_summary = ds.get("preprocessing")
        has_petugas = (
            bool(prep_summary.get("has_petugas", False))
            if isinstance(prep_summary, dict)
            else False
        )

        geocoding_summary = {
            "total": geo_counts["total"],
            "berhasil": geo_counts["berhasil"],
            "gagal": geo_counts["gagal"],
            "pending": geo_counts["pending"],
            "has_petugas": has_petugas,
            "gagal_items": gagal_items
        }

        # Hitung poligon batas convex hull via Shapely untuk K-Means dan HBCDP
        polygons_kmeans = {}
        polygons_hbcdp = {}
        if hc:
            pts_grouped_sql = """
                SELECT 
                    dp.latitude,
                    dp.longitude,
                    cl.nomor_cluster AS c_init,
                    COALESCE(ac.nomor_zona, cl.nomor_cluster) AS c_final
                FROM data_pengiriman dp
                INNER JOIN anggota_cluster ac ON dp.id_pengiriman = ac.id_pengiriman
                INNER JOIN cluster cl ON ac.id_cluster = cl.id_cluster
                WHERE dp.id_dataset = %s AND cl.id_clustering = %s
                  AND dp.latitude IS NOT NULL AND dp.longitude IS NOT NULL;
            """
            pts_grouped = query_db(pts_grouped_sql, (id_dataset, hc["id_clustering"]))
            if pts_grouped:
                from collections import defaultdict
                km_pts_map = defaultdict(list)
                hb_pts_map = defaultdict(list)
                for pr in pts_grouped:
                    latlng = (pr["latitude"], pr["longitude"])
                    if pr["c_init"] is not None:
                        km_pts_map[str(pr["c_init"])].append(latlng)
                    if pr["c_final"] is not None:
                        hb_pts_map[str(pr["c_final"])].append(latlng)
                for c_k, c_coords in km_pts_map.items():
                    polygons_kmeans[c_k] = compute_shapely_hull_latlng(c_coords)
                for c_k, c_coords in hb_pts_map.items():
                    polygons_hbcdp[c_k] = compute_shapely_hull_latlng(c_coords)

        aktual = get_actual_evaluation(id_dataset)
        if aktual and aktual["sidik_data"] != actual_evaluation_service.fingerprint(
            successful_dataset_points(id_dataset)
        ):
            aktual = None
        perbandingan = hc.pop("evaluasi_perbandingan", None) if hc else None
        if perbandingan and (
            not aktual or perbandingan.get("sidik_data") != aktual["sidik_data"]
        ):
            perbandingan = None

        # Format respon yang terintegrasi dengan frontend
        response_data = {
            "dataset": ds,
            "aktual": aktual,
            "perbandingan": perbandingan,
            "clustering": hc,
            "clusters_kmeans": clusters_kmeans,
            "optimasi": ho,
            "zonas_hbcdp": zonas_hbcdp,
            "geocoding_summary": geocoding_summary,
            "polygons": {
                "kmeans": polygons_kmeans,
                "hbcdp": polygons_hbcdp
            },
            "polygons_kmeans": polygons_kmeans,
            "polygons_hbcdp": polygons_hbcdp
        }
        return jsonify({"success": True, "data": response_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/<int:id_dataset>/points", methods=["GET"])
def get_dataset_points(id_dataset):
    """
    Mengambil titik-titik pengiriman suatu dataset beserta cluster penugasannya.
    Mendukung filter pencarian alamat/resi dan pagination.
    Memastikan tidak ada baris ganda dengan subquery hanya pada sesi clustering terakhir.
    """
    try:
        search = request.args.get("search", "").strip()

        # Periksa apakah dataset sudah memiliki hasil clustering
        hc_latest = query_db(
            "SELECT id_clustering FROM hasil_clustering WHERE id_dataset = %s ORDER BY id_clustering DESC LIMIT 1;",
            (id_dataset,),
            one=True
        )

        if hc_latest:
            # Hanya ambil titik yang benar-benar masuk dalam hasil clustering dataset ini
            sql = """
                SELECT
                    dp.id_pengiriman,
                    dp.nosi,
                    dp.petugas,
                    dp.alamat_asli,
                    dp.alamat_bersih,
                    dp.latitude,
                    dp.longitude,
                    dp.x_meter,
                    dp.y_meter,
                    dp.status_geocoding,
                    cl.nomor_cluster AS c_init,
                    COALESCE(ac.nomor_zona, cl.nomor_cluster) AS c_final,
                    CASE 
                        WHEN ac.nomor_zona IS NOT NULL AND ac.nomor_zona != cl.nomor_cluster THEN 'Berpindah'
                        ELSE 'Tetap'
                    END AS status
                FROM data_pengiriman dp
                INNER JOIN anggota_cluster ac ON dp.id_pengiriman = ac.id_pengiriman
                INNER JOIN cluster cl ON ac.id_cluster = cl.id_cluster
                WHERE dp.id_dataset = %s AND cl.id_clustering = %s
            """
            params = [id_dataset, hc_latest["id_clustering"]]

        else:
            # Jika belum dicluster, tampilkan titik dari data pengiriman
            sql = """
                SELECT
                    dp.id_pengiriman,
                    dp.nosi,
                    dp.petugas,
                    dp.alamat_asli,
                    dp.alamat_bersih,
                    dp.latitude,
                    dp.longitude,
                    dp.x_meter,
                    dp.y_meter,
                    dp.status_geocoding,
                    NULL AS c_init,
                    NULL AS c_final,
                    NULL AS status
                FROM data_pengiriman dp
                WHERE dp.id_dataset = %s
            """
            params = [id_dataset]

        if search:
            sql += " AND (dp.nosi ILIKE %s OR dp.alamat_asli ILIKE %s OR dp.alamat_bersih ILIKE %s OR dp.petugas ILIKE %s)"
            params.extend([f"%{search}%"] * 4)


        # Ambil seluruh titik pengiriman untuk ditampilkan pada peta
        sql += " ORDER BY dp.id_pengiriman ASC;"

        points = query_db(sql, params)

        # Normalisasi nama petugas untuk tampilan dashboard
        for point in points:
            point["petugas"] = actual_evaluation_service._petugas(point)

        return jsonify({
            "success": True,
            "data": points,
            "count": len(points)
        })


    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 3. REST API: Upload & Pipeline Clustering
# ============================================================================

def read_dataset_rows(file_stream, ext):
    """
    Membaca dataset pengiriman baik dari format .csv maupun .xlsx
    Mengembalikan: (headers, list of dict rows)
    """
    rows = []
    headers = []

    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        sheet = wb.active
        raw_rows = list(sheet.iter_rows(values_only=True))
        if raw_rows:
            headers = [str(c).strip() if c is not None else "" for c in raw_rows[0]]
            for r in raw_rows[1:]:
                if any(c is not None and str(c).strip() != "" for c in r):
                    row_dict = {}
                    for idx, col_name in enumerate(headers):
                        val = r[idx] if idx < len(r) else ""
                        row_dict[col_name] = str(val).strip() if val is not None else ""
                    rows.append(row_dict)

    elif ext == ".csv":
        content = file_stream.read().decode("utf-8", errors="replace")
        delimiter = ";" if content.splitlines()[0].count(";") > content.splitlines()[0].count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        for r in reader:
            if any(str(v).strip() != "" for v in r.values()):
                clean_r = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in r.items() if k}
                rows.append(clean_r)

    return headers, rows


@app.route("/api/preprocessing/progress/<upload_id>", methods=["GET"])
def get_preprocessing_progress(upload_id):
    try:
        UUID(upload_id)
    except ValueError:
        return jsonify({"success": False, "error": "upload_id tidak valid"}), 400

    with preprocessing_progress_lock:
        progress = preprocessing_progress.get(upload_id)
        data = dict(progress) if progress else {
            "total": 0, "processed": 0, "status": "NOT_STARTED"
        }

    total = data["total"]
    processed = data["processed"]
    data["percentage"] = round(processed * 100 / total) if total else 0
    return jsonify({"success": True, "data": data})


@app.route("/api/upload", methods=["POST"])
def upload_dataset():
    """
    Endpoint menerima file dataset pengiriman (.csv, .xlsx, .xls)
    dan menyimpannya ke tabel dataset serta data_pengiriman dengan pembersihan data otomatis.
    """
    upload_id = request.form.get("upload_id", "").strip()
    if upload_id:
        try:
            UUID(upload_id)
        except ValueError:
            return jsonify({"success": False, "error": "upload_id tidak valid"}), 400

    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "File tidak ditemukan dalam request"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "Nama file kosong"}), 400

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in [".csv", ".xlsx"]:
            return jsonify({
                "success": False,
                "error": "Format file tidak didukung. Harap gunakan format .csv atau .xlsx."
            }), 400

        headers, rows = read_dataset_rows(file.stream, ext)
        if not rows:
            return jsonify({"success": False, "error": f"File {ext} tidak memiliki baris data"}), 400

        # Validasi kolom wajib
        required_cols = [
    "Nosi",
    "Tgl Antaran Pertama",
    "Alamat",
    "Kota"
]
        col_map = {}
        for req in required_cols:
            matched = next((h for h in headers if req.lower() in h.lower()), None)
            if not matched:
                return jsonify({
                    "success": False,
                    "error": f"Format kolom template tidak valid. Kolom '{req}' tidak ditemukan."
                }), 400
            col_map[req] = matched
        petugas_col = next((h for h in headers if h.strip().casefold().startswith("petugas")), None)
        if petugas_col:
            col_map["Petugas"] = petugas_col

        tgl_col = col_map["Tgl Antaran Pertama"]

        # ============================================================
        # VALIDASI TANGGAL SELURUH BARIS
        # Satu file hanya boleh berisi satu tanggal pengantaran
        # ============================================================
        parsed_dates = []

        for r in rows:
            tanggal_raw = str(r.get(tgl_col, "")).strip()

            if not tanggal_raw:
                return jsonify({
                    "success": False,
                    "error": "Terdapat data dengan 'Tgl Antaran Pertama' kosong."
                }), 400

            tanggal_obj = None
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    tanggal_obj = datetime.strptime(
                        tanggal_raw.split()[0],
                        fmt
                    )
                    break
                except ValueError:
                    continue

            if tanggal_obj is None:
                return jsonify({
                    "success": False,
                    "error": (
                        f"Format tanggal tidak valid: '{tanggal_raw}'. "
                        "Gunakan format hari-bulan-tahun (contoh: 01/08/2025)."
                    )
                }), 400

            parsed_dates.append(
                tanggal_obj.strftime("%Y-%m-%d")
            )

        unique_dates = set(parsed_dates)
        if len(unique_dates) != 1:
            return jsonify({
                "success": False,
                "error": (
                    "Satu file hanya boleh berisi satu tanggal pengantaran. "
                    f"Ditemukan tanggal: {', '.join(sorted(unique_dates))}"
                )
            }), 400

        tanggal_data = parsed_dates[0]
        tanggal_display = datetime.strptime(tanggal_data, "%Y-%m-%d").strftime("%d/%m/%Y")

        # ============================================================
        # PREPROCESSING DATA (via PreprocessingService)
        # 1. Pemeriksaan Data Kosong
        # 2. Pemeriksaan Resi Duplikat
        # 3. Normalisasi Alamat
        # ============================================================
        if upload_id:
            with preprocessing_progress_lock:
                if upload_id in preprocessing_progress:
                    return jsonify({"success": False, "error": "upload_id sudah digunakan"}), 409
                preprocessing_progress[upload_id] = {
                    "total": len(rows), "processed": 0, "status": "PROCESSING"
                }

        def report_preprocessing(processed, total):
            set_preprocessing_progress(
                upload_id, processed=processed, total=total
            )

        prep_result = preprocessing_service.proses_dataset(
            rows, col_map, progress_callback=report_preprocessing
        )
        set_preprocessing_progress(upload_id, status="SAVING")
        summary = prep_result["summary"]
        valid_rows = prep_result["valid_rows"]

        total_awal = summary["total_awal"]
        total_eliminasi = summary["total_eliminasi"]
        total_valid = summary["total_valid"]
        empty_count = summary["rincian"]["data_kosong"]["count"]
        wilayah_count = 0
        dup_count = summary["rincian"]["resi_duplikat"]["count"]
        umum_count = 0
        jumlah_data = total_valid
        preprocessing_json = json.dumps(summary)

        # Seluruh data tereliminasi: preprocessing selesai,
        # tetapi tidak ada data yang dapat dilanjutkan.
        if jumlah_data == 0:
            set_preprocessing_progress(upload_id, status="COMPLETED")
            return jsonify({
                "success": True,
                "preprocessing_only": True,
                "message": (
                    f"Preprocessing selesai. Seluruh {total_awal} data "
                    "tereliminasi sehingga tidak ada data yang dapat "
                    "dilanjutkan ke proses geocoding."
                ),
                "data": {
                    "id_dataset": None,
                    "nama_file": filename,
                    "tanggal_data": tanggal_display,
                    "tanggal_data_iso": tanggal_data,
                    "total_awal": total_awal,
                    "jumlah_data": 0,
                    "total_valid": 0,
                    "eliminasi_wilayah": wilayah_count,
                    "eliminasi_kosong": empty_count,
                    "eliminasi_duplikat": dup_count,
                    "eliminasi_alamat_umum": umum_count,
                    "total_eliminasi": total_eliminasi,
                    "dieliminasi": total_eliminasi,
                    "preprocessing": summary
                }
            }), 200
        
        ds_insert_sql = """
            INSERT INTO dataset (
                nama_file,
                tanggal_data,
                jumlah_data,
                jumlah_kurir,
                status,
                total_awal,
                eliminasi_wilayah,
                eliminasi_kosong,
                eliminasi_duplikat,
                eliminasi_alamat_umum,
                total_eliminasi,
                preprocessing_json
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id_dataset;
        """

        
        ds_params = (
            filename,
            tanggal_data,
            jumlah_data,
            5,
            "UPLOADED",
            total_awal,
            wilayah_count,
            empty_count,
            dup_count,
            umum_count,
            total_eliminasi,
            preprocessing_json
        )


        dp_insert_sql = """
            INSERT INTO data_pengiriman
                (
                    id_dataset,
                    nosi,
                    alamat_asli,
                    alamat_bersih,
                    status_geocoding,
                    petugas,
                    kota
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """


        hist_sql = """
            INSERT INTO history_proses
                (id_dataset, jenis_proses, status)
            VALUES (%s, %s, %s);
        """

        # Simpan seluruh hasil upload dalam satu transaksi
        id_dataset = execute_upload_transaction(
            ds_insert_sql,
            ds_params,
            dp_insert_sql,
            valid_rows,
            hist_sql,
            geocoding_service
        )

        
        set_preprocessing_progress(upload_id, status="COMPLETED")

        filtered_info = []


        if empty_count > 0:
            filtered_info.append(
                f"{empty_count} data kosong"
            )

        if umum_count > 0:
            filtered_info.append(
                f"{umum_count} alamat umum"
            )

        if dup_count > 0:
            filtered_info.append(
                f"{dup_count} resi duplikat"
            )

        info_str = (
            f" ({', '.join(filtered_info)} dieliminasi)"
            if filtered_info else ""
        )
        return jsonify({
            "success": True,
            "message": (
                f"Dataset {filename} berhasil diunggah: "
                f"{jumlah_data} data valid siap dilanjutkan, "
                f"{total_eliminasi} data tereliminasi dari {total_awal} data awal."
            ),
            "data": {
                "id_dataset": id_dataset,
                "nama_file": filename,
                "tanggal_data": tanggal_display,
                "tanggal_data_iso": tanggal_data,
                "total_awal": total_awal,
                "jumlah_data": jumlah_data,
                "total_valid": jumlah_data,
                "eliminasi_wilayah": wilayah_count,
                "eliminasi_kosong": empty_count,
                "eliminasi_duplikat": dup_count,
                "eliminasi_alamat_umum": umum_count,
                "total_eliminasi": total_eliminasi,
                "dieliminasi": total_eliminasi,
                "preprocessing": summary
            }
        })

    except Exception as e:
        set_preprocessing_progress(upload_id, status="FAILED", error=str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/<int:id_dataset>/geocode", methods=["POST"])
def geocode_dataset_points(id_dataset):
    """
    Menjalankan proses geocoding pada dataset tertentu dengan batas jumlah titik (limit).
    Jika limit adalah None/'None'/null/kosong, memproses seluruh baris data.
    Jika limit berupa angka, memproses sejumlah angka tersebut.
    """
    try:
        req_data = request.get_json(silent=True) or {}
        # Pengaturan batas data geocoding: Diambil default dari Config.GEOCODING_LIMIT (dari .env)
        # Jika .env disetel ke None/kosong, memproses seluruh data
        # Jika .env disetel ke angka (contoh: 22), membatasi N data
        raw_limit = req_data.get("limit")
        if raw_limit is None:
            limit_n = Config.GEOCODING_LIMIT
        elif str(raw_limit).strip().lower() in ("", "none", "null", "all", "semua"):
            limit_n = None
        else:
            try:
                limit_n = int(raw_limit)
                if limit_n <= 0:
                    limit_n = None
            except (ValueError, TypeError):
                limit_n = Config.GEOCODING_LIMIT

        if limit_n is not None:
            pts_sql = """
                SELECT id_pengiriman, nosi, petugas, alamat_bersih,
                    alamat_asli, kota, latitude, longitude, x_meter, y_meter
                FROM data_pengiriman
                WHERE id_dataset = %s
                ORDER BY id_pengiriman ASC
                LIMIT %s;
            """
            points = query_db(pts_sql, (id_dataset, limit_n))
        else:
            pts_sql = """
                SELECT id_pengiriman, nosi, petugas, alamat_bersih,
                    alamat_asli, kota, latitude, longitude, x_meter, y_meter
                FROM data_pengiriman
                WHERE id_dataset = %s
                ORDER BY id_pengiriman ASC;
            """
            points = query_db(pts_sql, (id_dataset,))

        if not points:
            return jsonify({"success": False, "error": "Data pengiriman tidak ditemukan"}), 404

        # Inisialisasi progres geocoding
        with geocoding_progress_lock:
            if geocoding_progress.get(id_dataset, {}).get("status") in ("PROCESSING", "EVALUATING_ACTUAL"):
                return jsonify({"success": False, "error": "Geocoding dataset masih berjalan."}), 409
            geocoding_progress[id_dataset] = {
                "total": len(points),
                "processed": 0,
                "status": "PROCESSING"
            }
        
        berhasil_baru = 0
        gagal = 0
        berhasil_sudah_ada = 0
        gagal_items = []
        for index, p in enumerate(points):
            lat = p["latitude"]
            lng = p["longitude"]
            xm = p["x_meter"]
            ym = p["y_meter"]

            # Titik yang sudah memiliki koordinat lengkap
            if all(v is not None for v in (lat, lng, xm, ym)):
                execute_db(
                    """
                    UPDATE data_pengiriman
                    SET status_geocoding = 'SUCCESS'
                    WHERE id_pengiriman = %s
                    """,
                    (p["id_pengiriman"],)
                )
                berhasil_sudah_ada += 1

                with geocoding_progress_lock:
                    geocoding_progress[id_dataset]["processed"] = index + 1

                continue

            alamat_target = (
                p.get("alamat_bersih")
                or p.get("alamat_asli")
                or ""
            )

            geo = geocoding_service.geocode(
                alamat_target,
                p.get("kota") or ""
            )

            koordinat_lengkap = all(
                geo.get(k) is not None
                for k in (
                    "latitude",
                    "longitude",
                    "x_meter",
                    "y_meter"
                )
            )

            if geo.get("status") == "SUCCESS" and koordinat_lengkap:
                execute_db(
                    """
                    UPDATE data_pengiriman
                    SET latitude = %s,
                        longitude = %s,
                        x_meter = %s,
                        y_meter = %s,
                        status_geocoding = 'SUCCESS'
                    WHERE id_pengiriman = %s
                    """,
                    (
                        geo["latitude"],
                        geo["longitude"],
                        geo["x_meter"],
                        geo["y_meter"],
                        p["id_pengiriman"]
                    )
                )
                berhasil_baru += 1
            else:
 
                err_raw = str(geo.get("error") or "")
                err_lower = err_raw.casefold()

                # Google Maps tidak menemukan lokasi
                if (
                    "alamat tidak ditemukan" in err_lower
                    or "zero_results" in err_lower
                    or "tidak ada kandidat koordinat" in err_lower
                ):
                    keterangan = "Lokasi tidak ditemukan"

                # Google Maps menemukan kandidat,
                # tetapi wilayah administratif bukan Kota Malang
                elif (
                    "di luar wilayah kota malang" in err_lower
                    or "di luar poligon kota malang" in err_lower
                    or "di luar kota malang" in err_lower
                ):
                    keterangan = "Di luar wilayah Kota Malang"

                # Kesalahan API atau koneksi
                elif (
                    "api" in err_lower
                    or "key" in err_lower
                    or "menghubungi" in err_lower
                    or "permintaan ditolak" in err_lower
                    or "batas permintaan" in err_lower
                ):
                    keterangan = err_raw or "Permintaan API gagal"

                # Kegagalan lainnya
                else:
                    keterangan = err_raw or "Geocoding gagal"

                execute_db(
                    """
                    UPDATE data_pengiriman
                    SET latitude = NULL,
                        longitude = NULL,
                        x_meter = NULL,
                        y_meter = NULL,
                        status_geocoding = 'FAILED',
                        keterangan_geocoding = %s
                    WHERE id_pengiriman = %s
                    """,
                    (keterangan, p["id_pengiriman"])
                )
                gagal += 1
                gagal_items.append({
                    "no": len(gagal_items) + 1,
                    "resi": p.get("nosi") or "-",
                    "petugas": p.get("petugas") or "-",
                    "alamat": alamat_target,
                    "keterangan": keterangan
                })
            # Perbarui progres setelah satu alamat selesai diproses
            with geocoding_progress_lock:
                geocoding_progress[id_dataset]["processed"] = index + 1

        total_berhasil = berhasil_baru + berhasil_sudah_ada
        # Baseline selesai dan tersimpan sebelum respons sukses / tombol clustering siap.
        with geocoding_progress_lock:
            geocoding_progress[id_dataset]["status"] = "EVALUATING_ACTUAL"
        aktual = save_actual_evaluation(
            id_dataset,
            actual_evaluation_service.evaluate(successful_dataset_points(id_dataset))
        )


        # Tandai proses geocoding telah selesai
        with geocoding_progress_lock:
            geocoding_progress[id_dataset]["status"] = "COMPLETED"

        return jsonify({
            "success": True,
            "message": (
                f"Geocoding selesai: {total_berhasil} berhasil, "
                f"{gagal} gagal dari {len(points)} titik yang diperiksa."
            ),
            "data": {
                "id_dataset": id_dataset,
                "aktual": aktual,
                "total_points": len(points),
                "total_diproses": len(points),
                "berhasil": total_berhasil,
                "gagal": gagal,
                "gagal_items": gagal_items,
                "berhasil_baru": berhasil_baru,
                "berhasil_sudah_ada": berhasil_sudah_ada
            }
        })

    except Exception as e:
        app.logger.exception(
            "ERROR GEOCODING DATASET %s", id_dataset
        )

        with geocoding_progress_lock:
            if id_dataset in geocoding_progress:
                geocoding_progress[id_dataset]["status"] = "FAILED"

        return jsonify({"success": False, "error": str(e)}), 500


# Endpoint untuk membaca progres geocoding
@app.route("/api/dataset/<int:id_dataset>/geocode/progress", methods=["GET"])
def get_geocoding_progress(id_dataset):
    with geocoding_progress_lock:
        progress = geocoding_progress.get(id_dataset)

        if progress is None:
            return jsonify({
                "success": True,
                "data": {
                    "total": 0,
                    "processed": 0,
                    "percentage": 0,
                    "status": "NOT_STARTED"
                }
            })

        total = progress["total"]
        processed = progress["processed"]

        percentage = round(
            (processed / total) * 100
        ) if total > 0 else 0

        return jsonify({
            "success": True,
            "data": {
                "total": total,
                "processed": processed,
                "percentage": percentage,
                "status": progress["status"]
            }
        })


@app.route("/api/cluster/<int:id_dataset>", methods=["POST"])
def run_clustering(id_dataset):
    """
    Menjalankan K-Means dan HBCDP pada seluruh titik hasil geocoding.
    Baseline aktual wajib sudah tersimpan; endpoint ini tidak menghitung ulang aktual.
    """
    try:
        req_data = request.get_json(silent=True) or {}

        # Validasi K manual, terpisah dari jumlah kurir aktual.
        raw_k = req_data.get("k")

        if isinstance(raw_k, bool):
            return jsonify({
                "success": False,
                "error": "Jumlah cluster (K) harus berupa bilangan bulat."
            }), 400

        try:
            if isinstance(raw_k, float) and not raw_k.is_integer():
                raise ValueError

            if isinstance(raw_k, str) and not raw_k.strip().isdigit():
                raise ValueError

            k = int(raw_k)

        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "Jumlah cluster (K) wajib diisi dengan bilangan bulat."
            }), 400


       
        with geocoding_progress_lock:
            if geocoding_progress.get(id_dataset, {}).get("status") in ("PROCESSING", "EVALUATING_ACTUAL"):
                return jsonify({"success": False, "error": "Tunggu geocoding dan evaluasi aktual selesai."}), 409
        points = successful_dataset_points(id_dataset)
        aktual = get_actual_evaluation(id_dataset)
        if not aktual or aktual["sidik_data"] != actual_evaluation_service.fingerprint(points):
            return jsonify({
                "success": False,
                "error": "Baseline aktual belum tersedia atau data berubah. Selesaikan geocoding sebelum clustering."
            }), 409

        n_valid = len(points)

        if k < 2 or n_valid <= k:
            return jsonify({
                "success": False,
                "error": (
                    f"Jumlah titik valid = {n_valid}, sedangkan K = {k}. "
                    "Clustering memerlukan minimal 2 cluster "
                    "dan jumlah titik valid harus lebih besar dari K."
                )
            }), 400

        coords = [
            (p["x_meter"], p["y_meter"])
            for p in points
        ]

        # 1. Bersihkan hasil clustering sebelumnya untuk dataset ini agar tidak ada duplikasi
        execute_db("DELETE FROM hasil_clustering WHERE id_dataset = %s;", (id_dataset,))

        t_start = time.perf_counter()

        # 2. Jalankan KMeansService
        km_result = kmeans_service.clustering(coords, k=k)
        km_eval = kmeans_service.evaluasiCluster(coords, km_result["labels"], km_result["centroids"], k=k)

        # 3. Jalankan HBCDPService
        hb_result = hbcdp_service.optimasi(coords, km_result["labels"], km_result["centroids"], k=k)

        t_end = time.perf_counter()
        waktu_komputasi = round(t_end - t_start, 2)
        waktu_komputasi_str = f"{waktu_komputasi:.2f}".replace(".", ",") + " detik"

        # Evaluasi pembanding memakai resi yang sama, tanpa clustering ulang.
        perbandingan = actual_evaluation_service.compare(
            points, km_result["labels"], hb_result["final_labels"], k
        )
        perbandingan["sidik_data"] = aktual["sidik_data"]

        # 4. Simpan hasil_clustering ke DB
        hc_sql = """
            INSERT INTO hasil_clustering (
                id_dataset, jumlah_cluster, silhouette_score, dbi,
                waktu_komputasi, evaluasi_perbandingan
            ) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_clustering;
        """
        from psycopg2.extras import Json
        id_clustering = execute_db(hc_sql, (
            id_dataset, k, km_eval["silhouette_score"], km_eval["dbi"],
            waktu_komputasi, Json(perbandingan)
        ), returning_id=True)

        cluster_ids = []
        for c_idx, (cx, cy) in enumerate(km_result["centroids"]):
            c_count = km_result["counts"][c_idx]
            c_sql = """
                INSERT INTO cluster (id_clustering, nomor_cluster, centroid_x, centroid_y, jumlah_anggota)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_cluster;
            """
            id_cluster = execute_db(c_sql, (id_clustering, c_idx + 1, cx, cy, c_count), returning_id=True)
            cluster_ids.append(id_cluster)

        # 5. Simpan anggota_cluster lengkap dengan cluster awal dan nomor_zona akhir HBCDP
        ac_sql = """
            INSERT INTO anggota_cluster (id_cluster, id_pengiriman, jarak_ke_centroid, nomor_zona)
            VALUES (%s, %s, %s, %s);
        """
        for i, p in enumerate(points):
            c_label = km_result["labels"][i]
            assigned_cluster_id = cluster_ids[c_label]
            dist = kmeans_service.hitungJarakEuclidean(coords[i], km_result["centroids"][c_label])
            final_z_num = hb_result["final_labels"][i] + 1
            execute_db(ac_sql, (assigned_cluster_id, p["id_pengiriman"], dist, final_z_num))

        # 6. Simpan hasil_optimasi beserta metrik dan riwayat 4 tahap steps_json
        ho_sql = """
            INSERT INTO hasil_optimasi (id_clustering, nilai_z1, nilai_z2, silhouette_score, dbi, steps_json, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_optimasi;
        """
        id_optimasi = execute_db(
            ho_sql,
            (
                id_clustering,
                hb_result["z1_final"],
                hb_result["z2_final"],
                hb_result.get("silhouette", 0.0),
                hb_result.get("dbi", 0.0),
                json.dumps(hb_result["steps"]),
                "SUCCESS"
            ),
            returning_id=True
        )

        # 7. Hitung poligon batas convex hull via Shapely untuk K-Means dan HBCDP
        polygons_kmeans = {}
        polygons_hbcdp = {}
        for c_idx in range(k):
            c_num = str(c_idx + 1)
            km_pts = [
                (float(p["latitude"]), float(p["longitude"]))
                for i, p in enumerate(points)
                if km_result["labels"][i] == c_idx and p["latitude"] is not None and p["longitude"] is not None
            ]
            hb_pts = [
                (float(p["latitude"]), float(p["longitude"]))
                for i, p in enumerate(points)
                if hb_result["final_labels"][i] == c_idx and p["latitude"] is not None and p["longitude"] is not None
            ]
            polygons_kmeans[c_num] = compute_shapely_hull_latlng(km_pts)
            polygons_hbcdp[c_num] = compute_shapely_hull_latlng(hb_pts)

        # Simpan zona_kurir poligon batas geografis ke PostgreSQL
        zk_sql = """
            INSERT INTO zona_kurir (id_optimasi, nomor_zona, jumlah_anggota, polygon)
            VALUES (%s, %s, %s, %s);
        """
        for z in hb_result["zonas"]:
            z_num = z["nomor_zona"]
            poly_coords = polygons_hbcdp.get(str(z_num), [])
            poly_str = json.dumps({"type": "Polygon", "coordinates": poly_coords})
            execute_db(zk_sql, (id_optimasi, z_num, z["jumlah_anggota"], poly_str))

        execute_db("UPDATE dataset SET status='COMPLETED', jumlah_kurir=%s WHERE id_dataset=%s;", (k, id_dataset))
        execute_db("INSERT INTO history_proses (id_dataset, id_clustering, id_optimasi, jenis_proses, status) VALUES (%s, %s, %s, %s, %s);",
                   (id_dataset, id_clustering, id_optimasi, "HBCDP_OPTIMIZATION", "COMPLETED"))

        return jsonify({
            "success": True,
            "message": "Proses K-Means dan Optimasi HBCDP berhasil diselesaikan",
            "data": {
                "id_clustering": id_clustering,
                "id_optimasi": id_optimasi,
                "aktual": aktual,
                "perbandingan": perbandingan,
                "k": k,
                "jumlah_kurir": k,
                "n": n_valid,
                "waktu_komputasi": waktu_komputasi,
                "waktu_komputasi_str": waktu_komputasi_str,
                "evaluasi_kmeans": km_eval,
                "evaluasi_hbcdp": {
                    "z1": hb_result["z1_final"],
                    "z2": hb_result["z2_final"],
                    "steps": hb_result["steps"]
                },
                "polygons": {
                    "kmeans": polygons_kmeans,
                    "hbcdp": polygons_hbcdp
                },
                "polygons_kmeans": polygons_kmeans,
                "polygons_hbcdp": polygons_hbcdp
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 4. REST API: Unduhan Template & Ekspor Hasil
# ============================================================================

@app.route("/api/download/template/<format_type>")
def download_template(format_type):
    """Menyediakan unduhan template file dataset pengiriman (CSV / Excel .xlsx asli)."""
    if format_type.lower() in ["excel", "xlsx"]:
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Template Pengiriman")

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#E85D04",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        cell_format = workbook.add_format({
            "border": 1,
            "valign": "vcenter"
        })
        center_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        headers = ["No.", "Nosi", "Tgl Antaran Pertama", "Alamat", "Kota", "Petugas"]
        for col_idx, h in enumerate(headers):
            worksheet.write(0, col_idx, h, header_format)

        sample_rows = [
            [1, "nosi_1", "01/08/2025", "Jl. Contoh No. 1", "Malang", "Kurir A"],
            [2, "nosi_2", "01/08/2025", "Jl. Contoh No. 2", "Malang", "Kurir B"],
            [3, "nosi_3", "01/08/2025", "Jl. Contoh No. 3", "Malang", "Kurir A"],
            [4, "nosi_4", "01/08/2025", "Jl. Contoh No. 4", "Malang", "Kurir B"],
            [5, "nosi_5", "01/08/2025", "Jl. Contoh No. 5", "Malang", ""],
        ]

        for r_idx, row in enumerate(sample_rows, start=1):
            worksheet.write(r_idx, 0, row[0], center_format)
            worksheet.write(r_idx, 1, row[1], cell_format)
            worksheet.write(r_idx, 2, row[2], center_format)
            worksheet.write(r_idx, 3, row[3], cell_format)
            worksheet.write(r_idx, 4, row[4], cell_format)

            worksheet.write(r_idx, 5, row[5], cell_format)
        worksheet.set_column(0, 0, 6)
        worksheet.set_column(1, 1, 14)
        worksheet.set_column(2, 2, 22)
        worksheet.set_column(3, 3, 35)
        worksheet.set_column(4, 4, 15)
        worksheet.set_column(5, 5, 20)

        workbook.close()
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="Template_Dataset_GeoKurir.xlsx"
        )
    else:
        csv_text = (
            "No.,Nosi,Tgl Antaran Pertama,Alamat,Kota,Petugas\n"
            "1,nosi_1,01/08/2025,Jl. Contoh No. 1,Malang,Kurir A\n"
            "2,nosi_2,01/08/2025,Jl. Contoh No. 2,Malang,Kurir B\n"
            "3,nosi_3,01/08/2025,Jl. Contoh No. 3,Malang,Kurir A\n"
            "4,nosi_4,01/08/2025,Jl. Contoh No. 4,Malang,Kurir B\n"
            "5,nosi_5,01/08/2025,Jl. Contoh No. 5,Malang,\n"
        )
        mem = io.BytesIO(csv_text.encode("utf-8"))
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name="Template_Dataset_GeoKurir.csv"
        )


@app.route("/api/download/export/<int:id_dataset>")
def export_result_csv(id_dataset):
    """Mengekspor seluruh data pengiriman beserta zona cluster hasil akhir sebagai file CSV atau Excel."""
    try:
        format_type = request.args.get("format", "csv").lower()

        sql = """
            SELECT
                dp.id_pengiriman,
                dp.nosi,
                dp.petugas,
                dp.alamat_asli,
                dp.alamat_bersih,
                dp.latitude,
                dp.longitude,
                cl.nomor_cluster AS cluster_awal,
                COALESCE(ac.nomor_zona, cl.nomor_cluster) AS cluster_final,
                CASE
                    WHEN ac.nomor_zona IS NOT NULL
                         AND ac.nomor_zona != cl.nomor_cluster
                    THEN 'Berpindah'
                    ELSE 'Tetap'
                END AS status
            FROM data_pengiriman dp
            INNER JOIN anggota_cluster ac
                ON dp.id_pengiriman = ac.id_pengiriman
            INNER JOIN cluster cl
                ON ac.id_cluster = cl.id_cluster
            WHERE dp.id_dataset = %s
              AND cl.id_clustering = (
                  SELECT hc.id_clustering
                  FROM hasil_clustering hc
                  WHERE hc.id_dataset = %s
                  ORDER BY hc.id_clustering DESC
                  LIMIT 1
              )
              AND dp.status_geocoding = 'SUCCESS'
              AND dp.latitude IS NOT NULL
              AND dp.longitude IS NOT NULL
              AND dp.x_meter IS NOT NULL
              AND dp.y_meter IS NOT NULL
            ORDER BY dp.id_pengiriman ASC;
        """
        rows = query_db(sql, (id_dataset, id_dataset))

        ds_tgl_row = query_db("SELECT tanggal_data::text FROM dataset WHERE id_dataset = %s;", (id_dataset,), one=True)
        tgl_str = "-"
        if ds_tgl_row and ds_tgl_row.get("tanggal_data"):
            try:
                tgl_str = datetime.strptime(str(ds_tgl_row["tanggal_data"]), "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                tgl_str = str(ds_tgl_row["tanggal_data"])


        if not rows:
            return jsonify({
                "success": False,
                "error": "Belum ada titik hasil clustering yang dapat diekspor."
            }), 409

        if format_type in ["excel", "xlsx"]:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            worksheet = workbook.add_worksheet("Hasil Zonasi")

            header_format = workbook.add_format({
                "bold": True,
                "bg_color": "#0B192C",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter"
            })
            cell_format = workbook.add_format({"border": 1, "valign": "vcenter"})
            center_format = workbook.add_format({"border": 1, "align": "center", "valign": "vcenter"})

            headers = ["No", "No Resi", "Tgl Antaran Pertama", "Alamat Asli", "Alamat Bersih", "Latitude", "Longitude", "Cluster_KMeans", "Cluster_HBCDP", "Status", "Petugas Aktual"]
            for col_idx, h in enumerate(headers):
                worksheet.write(0, col_idx, h, header_format)

            for idx, r in enumerate(rows):
                resi = r["nosi"] or ""
                worksheet.write(idx + 1, 0, idx + 1, center_format)
                worksheet.write(idx + 1, 1, resi, center_format)
                worksheet.write(idx + 1, 2, tgl_str, center_format)
                worksheet.write(idx + 1, 3, r["alamat_asli"], cell_format)
                worksheet.write(idx + 1, 4, r["alamat_bersih"], cell_format)
                worksheet.write(idx + 1, 5, r["latitude"], cell_format)
                worksheet.write(idx + 1, 6, r["longitude"], cell_format)
                worksheet.write(idx + 1, 7, f"Cluster {r['cluster_awal']}" if r["cluster_awal"] is not None else "", center_format)
                worksheet.write(idx + 1, 8, f"Cluster {r['cluster_final']}" if r["cluster_final"] is not None else "", center_format)
                worksheet.write(idx + 1, 9, r["status"], center_format)
                worksheet.write(idx + 1, 10, r["petugas"] or "", cell_format)

            worksheet.set_column(0, 0, 6)
            worksheet.set_column(1, 1, 16)
            worksheet.set_column(2, 3, 35)
            worksheet.set_column(4, 5, 12)
            worksheet.set_column(6, 7, 16)
            worksheet.set_column(8, 8, 12)
            worksheet.set_column(10, 10, 24)

            workbook.close()
            output.seek(0)
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"Hasil_Clustering_Dataset_{id_dataset}.xlsx"
            )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["No", "No Resi", "Tgl Antaran Pertama", "Alamat Asli", "Alamat Bersih", "Latitude", "Longitude", "Cluster_KMeans", "Cluster_HBCDP", "Status", "Petugas Aktual"])

        for idx, r in enumerate(rows):
            resi = r["nosi"] or ""
            writer.writerow([
                idx + 1,
                resi,
                tgl_str,
                r["alamat_asli"],
                r["alamat_bersih"],
                r["latitude"],
                r["longitude"],
                f"Cluster {r['cluster_awal']}" if r["cluster_awal"] is not None else "",
                f"Cluster {r['cluster_final']}" if r["cluster_final"] is not None else "",
                r["status"],
                r["petugas"] or ""
            ])

        mem = io.BytesIO(output.getvalue().encode("utf-8"))
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"Hasil_Clustering_Dataset_{id_dataset}.csv"
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ============================================================================
# REST API: Ekspor Peta PNG menggunakan Playwright
# ============================================================================

@app.route("/api/download/map/<int:id_dataset>/<mode>", methods=["GET"])
def export_map_png(id_dataset, mode):
    import math
    from playwright.sync_api import sync_playwright

    filenames = {
        "aktual": "Peta_Aktual_PT_Pos.png",
        "kmeans": "Peta_KMeans_Awal.png",
        "hbcdp": "Peta_HBCDP_Hasil_Akhir.png"
    }

    if mode not in filenames:
        return jsonify({
            "success": False,
            "error": "Jenis peta tidak valid."
        }), 400

    # Pastikan dataset benar-benar ada.
    dataset = query_db(
        "SELECT id_dataset FROM dataset WHERE id_dataset = %s;",
        (id_dataset,),
        one=True
    )

    if not dataset:
        return jsonify({
            "success": False,
            "error": "Dataset tidak ditemukan."
        }), 404

    try:
        map_width = int(request.args.get("width", 1600))
        map_height = int(request.args.get("height", 900))

        if not (320 <= map_width <= 2560):
            raise ValueError("Lebar peta tidak valid.")

        if not (240 <= map_height <= 1600):
            raise ValueError("Tinggi peta tidak valid.")

        viewport_width = max(map_width, 1280)
        viewport_height = max(map_height, 900)

        lat_raw = request.args.get("lat")
        lng_raw = request.args.get("lng")
        zoom_raw = request.args.get("zoom")

        has_map_position = all(
            value is not None
            for value in (lat_raw, lng_raw, zoom_raw)
        )

        if has_map_position:
            lat = float(lat_raw)
            lng = float(lng_raw)
            zoom = int(zoom_raw)

            if not (
                math.isfinite(lat)
                and math.isfinite(lng)
                and -90 <= lat <= 90
                and -180 <= lng <= 180
                and 1 <= zoom <= 19
            ):
                raise ValueError("Posisi peta tidak valid.")
        elif any(
            value is not None
            for value in (lat_raw, lng_raw, zoom_raw)
        ):
            raise ValueError(
                "Latitude, longitude, dan zoom harus dikirim bersama."
            )

    except (ValueError, TypeError) as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 400

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            try:
                page = browser.new_page(
                    viewport={
                        "width": viewport_width,
                        "height": viewport_height
                    },
                    device_scale_factor=1
                )

                # Buka halaman dari dalam container Flask.
                url = f"http://127.0.0.1:{Config.PORT}/zona"

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                # Tunggu daftar dataset selesai dimuat.
                page.wait_for_function(
                    """datasetId => {
                        const selector = document.getElementById(
                            'select-process-dashboard'
                        );

                        return selector &&
                            Array.from(selector.options).some(
                                option => option.value === `db_${datasetId}`
                            );
                    }""",
                    arg=id_dataset,
                    timeout=30000
                )

                # Pilih dataset yang akan diekspor.
                page.evaluate(
                    """datasetId => {
                        const selector = document.getElementById(
                            'select-process-dashboard'
                        );

                        if (!selector) {
                            throw new Error('Dropdown dataset tidak ditemukan.');
                        }

                        selector.value = `db_${datasetId}`;

                        selector.dispatchEvent(
                            new Event('change', { bubbles: true })
                        );
                    }""",
                    id_dataset
                )

                # Tunggu titik dataset tersedia di frontend.
                page.wait_for_function(
                    """datasetId => {
                        const key = `db_${datasetId}`;

                        return (
                            typeof DATASETS !== 'undefined' &&
                            DATASETS[key] &&
                            Array.isArray(DATASETS[key].points) &&
                            DATASETS[key].points.length > 0
                        );
                    }""",
                    arg=id_dataset,
                    timeout=30000
                )

                # Pilih tab peta.
                tab_ids = {
                    "aktual": "#tab-aktual",
                    "kmeans": "#tab-kmeans",
                    "hbcdp": "#tab-hbcdp"
                }

                page.locator(tab_ids[mode]).click()

                # Tunggu proses render cluster yang dijadwalkan JavaScript.
                page.wait_for_timeout(1000)

                # Tunggu peta Leaflet dan titiknya dirender.
                page.wait_for_function(
                    """() => {
                        const map = document.getElementById(
                            'map-zona-large'
                        );

                        return map &&
                            map.classList.contains('leaflet-container') &&
                            map.querySelectorAll(
                                '.leaflet-interactive, .leaflet-marker-icon'
                            ).length > 0;
                    }""",
                    timeout=30000
                )

                # Samakan ukuran peta dengan tampilan frontend.
                page.evaluate(
                    """size => {
                        const element = document.getElementById(
                            'map-zona-large'
                        );

                        const map = mapManager.maps['map-zona-large'];

                        if (!element || !map) {
                            throw new Error('Peta Leaflet belum tersedia.');
                        }

                        element.style.width = `${size.width}px`;
                        element.style.height = `${size.height}px`;

                        map.invalidateSize({
                            pan: false,
                            animate: false
                        });
                    }""",
                    {
                        "width": map_width,
                        "height": map_height
                    }
                )

                # Terapkan posisi dan zoom yang sedang dilihat pengguna.
                if has_map_position:
                    page.evaluate(
                        """position => {
                            const map = mapManager.maps['map-zona-large'];

                            map.stop();
                            map.closePopup();

                            map.setView(
                                [position.lat, position.lng],
                                position.zoom,
                                { animate: false }
                            );
                        }""",
                        {
                            "lat": lat,
                            "lng": lng,
                            "zoom": zoom
                        }
                    )

                # Tunggu tile peta selesai dimuat.
                try:
                    page.wait_for_function(
                        """() => {
                            const element = document.getElementById(
                                'map-zona-large'
                            );

                            if (!element) return false;

                            const tiles = Array.from(
                                element.querySelectorAll('.leaflet-tile')
                            );

                            return tiles.length > 0 &&
                                tiles.every(tile => tile.complete);
                        }""",
                        timeout=15000
                    )
                except Exception:
                    app.logger.warning(
                        "Sebagian tile peta belum selesai dimuat."
                    )

                # Beri kesempatan Leaflet menyelesaikan rendering.
                page.wait_for_timeout(500)

                # Pastikan render ulang tidak mengubah posisi dan zoom.
                if has_map_position:
                    actual_position = page.evaluate(
                        """() => {
                            const map = mapManager.maps['map-zona-large'];
                            const center = map.getCenter();

                            return {
                                lat: center.lat,
                                lng: center.lng,
                                zoom: map.getZoom()
                            };
                        }"""
                    )

                    app.logger.info(
                        "Ekspor peta: diminta=(%s, %s, %s), aktual=%s",
                        lat,
                        lng,
                        zoom,
                        actual_position
                    )

                    if (
                        actual_position["zoom"] != zoom
                        or abs(actual_position["lat"] - lat) > 0.000001
                        or abs(actual_position["lng"] - lng) > 0.000001
                    ):
                        page.evaluate(
                            """position => {
                                const map = mapManager.maps['map-zona-large'];

                                map.stop();
                                map.setView(
                                    [position.lat, position.lng],
                                    position.zoom,
                                    { animate: false }
                                );
                            }""",
                            {"lat": lat, "lng": lng, "zoom": zoom}
                        )

                        page.wait_for_timeout(1000)

                # Ambil elemen peta saja, tanpa dashboard.
                png_bytes = page.locator(
                    "#map-zona-large"
                ).screenshot(
                    type="png",
                    animations="disabled",
                    timeout=30000
                )

            finally:
                browser.close()

        return send_file(
            io.BytesIO(png_bytes),
            mimetype="image/png",
            as_attachment=True,
            download_name=filenames[mode]
        )

    except Exception:
        app.logger.exception(
            "Gagal mengekspor peta dataset %s mode %s",
            id_dataset,
            mode
        )

        return jsonify({
            "success": False,
            "error": (
                "Ekspor peta gagal. Periksa log Flask untuk detail."
            )
        }), 500

@app.route("/api/health")
def healthcheck():
    """Healthcheck endpoint untuk memeriksa koneksi database PostgreSQL."""
    try:
        res = query_db("SELECT 1 AS ok;", one=True)
        return jsonify({"status": "HEALTHY", "database": "CONNECTED", "ok": res["ok"]})
    except Exception as e:
        return jsonify({"status": "UNHEALTHY", "database": "DISCONNECTED", "error": str(e)}), 500


# ============================================================================
# 5. Server Runner
# ============================================================================

if __name__ == "__main__":
    print(f"============================================================")
    print(f"  GeoKurir Malang — Flask Web Server Running")
    print(f"  Akses di http://localhost:{Config.PORT}")
    print(f"  Terhubung ke PostgreSQL di {Config.DB_HOST}:{Config.DB_PORT}")
    print(f"============================================================")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
