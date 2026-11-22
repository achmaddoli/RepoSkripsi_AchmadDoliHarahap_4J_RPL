import os
import sys
import psycopg2
from config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(BASE_DIR, "database", "01_schema.sql")
MIGRATIONS_DIR = os.path.join(BASE_DIR, "database", "migrations")


def apply_pending_migrations(conn):
    """Apply additive SQL and record each version in the caller's transaction."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
    for filename in sorted(os.listdir(MIGRATIONS_DIR)):
        filepath = os.path.join(MIGRATIONS_DIR, filename)
        if not filename.endswith(".sql") or not os.path.isfile(filepath) or filename in applied:
            continue
        run_sql_file(conn, filepath)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (filename,))
        print(f"  [OK] {filename}")


def lock_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("SET LOCAL lock_timeout = '10s'")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('geokurir_schema_migrations'))")


def migrate_up():
    """Preserve data and atomically apply every outstanding migration."""
    conn = get_connection()
    try:
        with conn:
            lock_migrations(conn)
            apply_pending_migrations(conn)
    finally:
        conn.close()
    print("[SELESAI] Migrasi incremental selesai; data yang ada dipertahankan.")

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
            lock_migrations(conn)
            print("2. Membuat ulang skema kosong dari database/01_schema.sql...")
            run_sql_file(conn, SCHEMA_FILE)
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS schema_migrations")
            # Current schema already includes these changes; repeat-safe SQL
            # records a matching ledger, including after a previous fresh/up.
            apply_pending_migrations(conn)
    finally:
        conn.close()

    print("3. Memeriksa status tabel...")
    status()

    print("============================================================")
    print("  [SELESAI] Database berhasil di-migrate fresh!")
    print("============================================================")

def status():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            tables = [
                "dataset",
                "data_pengiriman",
                "evaluasi_aktual",
                "hasil_clustering",
                "cluster",
                "anggota_cluster",
                "hasil_optimasi",
                "zona_kurir",
                "history_proses",
                "schema_migrations",
            ]
            print("\n--- RINGKASAN DATA DATABASE ---")
            for tbl in tables:
                cur.execute("SELECT to_regclass(%s)", (tbl,))
                if cur.fetchone()[0] is None:
                    print(f"  • {tbl.ljust(20)}: belum tersedia")
                    continue
                cur.execute(f"SELECT count(*) FROM {tbl};")
                cnt = cur.fetchone()[0]
                print(f"  • {tbl.ljust(20)}: {cnt} baris")
    finally:
        conn.close()

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if action in ["fresh", "migrate:fresh", "reset"]:
        migrate_fresh()
    elif action == "up":
        migrate_up()
    elif action in ["status"]:
        status()
    else:
        print(f"Aksi tidak dikenal: '{action}'. Gunakan 'up', 'fresh', atau 'status'.")
        sys.exit(2)
