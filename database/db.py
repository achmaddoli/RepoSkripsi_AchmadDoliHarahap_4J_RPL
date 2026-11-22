import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config

@contextmanager
def get_db_connection():
    """Context manager for obtaining a database connection with auto-commit/rollback."""
    conn = psycopg2.connect(**Config.get_db_connection_params())
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def query_db(query, params=None, one=False):
    """Execute a query and return results as dictionaries."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if cur.description is None:
                return None
            records = cur.fetchall()
            return (records[0] if records else None) if one else records

def execute_db(query, params=None, returning_id=False):
    """Execute INSERT/UPDATE/DELETE query and optionally return generated ID."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if returning_id:
                inserted_id = cur.fetchone()[0]
                return inserted_id
            return cur.rowcount




def execute_upload_transaction(
    ds_insert_sql,
    ds_params,
    dp_insert_sql,
    valid_rows,
    hist_sql,
    geocoding_service
):
    """
    Menyimpan dataset, data pengiriman, dan riwayat upload
    dalam satu transaksi PostgreSQL.

    Jika satu operasi gagal, seluruh transaksi dibatalkan.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # 1. Simpan metadata dataset
            cur.execute(ds_insert_sql, ds_params)
            id_dataset = cur.fetchone()[0]

            # 2. Simpan seluruh data pengiriman valid
            for item in valid_rows:
                if isinstance(item, dict):
                    resi = item.get("resi", "")
                    alamat_asli = item.get("alamat_asli", "")
                    alamat_bersih = item.get("alamat_bersih", "")
                    petugas = item.get("petugas")
                    kota = item.get("kota", "")
                else:
                    resi = item[0]
                    alamat_asli = item[1]
                    alamat_bersih = item[2]
                    petugas = item[3] if len(item) > 3 else None
                    kota = item[4] if len(item) > 4 else ""

                cur.execute(
                    dp_insert_sql,
                    (
                        id_dataset,
                        resi,
                        alamat_asli,
                        alamat_bersih,
                        "PENDING",
                        petugas,
                        kota
                    )
                )

            # 3. Catat riwayat upload sekali saja
            # setelah seluruh data pengiriman tersimpan
            cur.execute(
                hist_sql,
                (
                    id_dataset,
                    "UPLOAD",
                    "COMPLETED"
                )
            )

            # 4. Kembalikan ID dataset
            return id_dataset


def get_actual_evaluation(id_dataset):
    """Baseline tersimpan; membaca tidak pernah memicu perhitungan ulang."""
    return query_db("""
        SELECT id_evaluasi, id_dataset, jumlah_titik_geocoding,
               jumlah_titik_evaluasi, jumlah_kurir_aktual,
               silhouette_score, dbi, z1, status_evaluasi, alasan_na,
               distribusi, sidik_data, dihitung_pada::text
        FROM evaluasi_aktual WHERE id_dataset = %s;
    """, (id_dataset,), one=True)


def save_actual_evaluation(id_dataset, evaluation):
    """Simpan satu baseline untuk keadaan titik/Petugas dataset saat ini."""
    from psycopg2.extras import Json

    return query_db("""
        INSERT INTO evaluasi_aktual (
            id_dataset, jumlah_titik_geocoding, jumlah_titik_evaluasi,
            jumlah_kurir_aktual, silhouette_score, dbi, z1,
            status_evaluasi, alasan_na, distribusi, sidik_data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_dataset) DO UPDATE SET
            jumlah_titik_geocoding = EXCLUDED.jumlah_titik_geocoding,
            jumlah_titik_evaluasi = EXCLUDED.jumlah_titik_evaluasi,
            jumlah_kurir_aktual = EXCLUDED.jumlah_kurir_aktual,
            silhouette_score = EXCLUDED.silhouette_score,
            dbi = EXCLUDED.dbi,
            z1 = EXCLUDED.z1,
            status_evaluasi = EXCLUDED.status_evaluasi,
            alasan_na = EXCLUDED.alasan_na,
            distribusi = EXCLUDED.distribusi,
            sidik_data = EXCLUDED.sidik_data,
            dihitung_pada = CURRENT_TIMESTAMP
        RETURNING id_evaluasi, id_dataset, jumlah_titik_geocoding,
                  jumlah_titik_evaluasi, jumlah_kurir_aktual,
                  silhouette_score, dbi, z1, status_evaluasi, alasan_na,
                  distribusi, sidik_data, dihitung_pada::text;
    """, (
        id_dataset, evaluation["jumlah_titik_geocoding"],
        evaluation["jumlah_titik_evaluasi"], evaluation["jumlah_kurir_aktual"],
        evaluation["silhouette_score"], evaluation["dbi"], evaluation["z1"],
        evaluation["status_evaluasi"], evaluation["alasan_na"],
        Json(evaluation["distribusi"]), evaluation["sidik_data"]
    ), one=True)
