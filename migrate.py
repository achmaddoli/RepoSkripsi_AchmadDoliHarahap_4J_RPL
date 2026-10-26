import os
import sys
import psycopg2
from config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(BASE_DIR, "database", "01_schema.sql")

def get_connection():
    return psycopg2.connect(**Config.get_db_connection_params())

def run_sql_file(conn, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)

def migrate_fresh():
    print("============================================================")
    print("  GeoKurir Malang — Database Migrate Fresh")
    print("============================================================")
    print("1. Menghubungkan ke PostgreSQL...")
    conn = get_connection()
    print("   [OK] Terhubung ke", Config.DB_NAME, "di", f"{Config.DB_HOST}:{Config.DB_PORT}")

    try:
        # Buat ulang skema kosong dalam satu transaksi. Kegagalan
        # membatalkan penggantian sehingga database sebelumnya tetap utuh.
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '10s'")
            print("2. Membuat ulang skema kosong dari database/01_schema.sql...")
            run_sql_file(conn, SCHEMA_FILE)
    finally:
        conn.close()

    print("3. Memeriksa status tabel...")
    status()

    print("============================================================")
    print("  [SELESAI] Database berhasil di-migrate fresh!")
    print("============================================================")

def status():
    conn = get_connection()
    with conn.cursor() as cur:
        tables = [
            "dataset",
            "data_pengiriman",
            "hasil_clustering",
            "cluster",
            "anggota_cluster",
            "hasil_optimasi",
            "zona_kurir",
            "history_proses"
        ]
        print("\n--- RINGKASAN DATA DATABASE ---")
        for tbl in tables:
            cur.execute(f"SELECT count(*) FROM {tbl};")
            cnt = cur.fetchone()[0]
            print(f"  • {tbl.ljust(20)}: {cnt} baris")
    conn.close()

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if action in ["fresh", "migrate:fresh", "reset"]:
        migrate_fresh()
    elif action in ["status"]:
        status()
    else:
        print(f"Aksi tidak dikenal: '{action}'. Gunakan 'fresh' atau 'status'.")
