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
            for resi, alamat_asli, _ in valid_rows:
                alamat_bersih = (
                    geocoding_service.bersihkanAlamat(alamat_asli)
                )

                cur.execute(
                    dp_insert_sql,
                    (
                        id_dataset,
                        resi,
                        alamat_asli,
                        alamat_bersih,
                        "PENDING"
                    )
                )

            # 3. Catat riwayat upload
            cur.execute(
                hist_sql,
                (
                    id_dataset,
                    "UPLOAD",
                    "COMPLETED"
                )
            )

            return id_dataset
