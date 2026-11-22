# Setup Database PostgreSQL dengan Docker — GeoKurir Malang

## Database baru dimulai kosong

`database/01_schema.sql` berisi sembilan tabel aplikasi, tanpa data pengiriman.
Docker Compose menjalankan skema ini hanya pada volume PostgreSQL baru.
Saat startup, web menerapkan migrasi tambahan melalui `python migrate.py up`
dan mencatat versinya dalam `schema_migrations`. Dump tidak diimpor otomatis.

- Instalasi baru dengan volume baru: semua tabel kosong, ID dimulai dari 1.
- Restart/deploy ulang dengan volume yang sama: data tetap tersimpan.
- Pindah perangkat: salin kode dan buat `.env` baru; jangan pindahkan volume
  PostgreSQL atau memulihkan dump jika ingin mulai kosong.

Dashboard kosong menampilkan ajakan mengunggah dataset. `02_seed.sql` dan
`seed_dataset1.py` adalah contoh lama yang tidak dijalankan otomatis.

### Memeriksa atau mereset database yang sudah ada

`python migrate.py` dan `python migrate.py status` hanya memeriksa jumlah data.
Upgrade tanpa menghapus data:

```sh
docker compose exec -T web python migrate.py up
docker compose exec -T web python migrate.py status
```

`database/migrations/001_actual_evaluation.sql` menambahkan Petugas opsional,
tabel `evaluasi_aktual`, dan `hasil_clustering.evaluasi_perbandingan`.
Perintah `up` dapat diulang; versi yang selesai tidak diterapkan ulang.

Reset manual **menghapus semua data**. Jika memang ingin mengosongkan database
yang sudah ada, cadangkan dahulu, lalu gunakan perintah berikut dari lingkungan
Python yang sudah dipasangi dependensi:

```bash
# Simpan cadangan di luar folder website (misalnya direktori pribadi).
docker compose exec -T postgres pg_dump -U geokurir -d geokurir_db > /tmp/geokurir-before-restore.sql

# Menghapus data dan membuat ulang skema kosong menggunakan konfigurasi DB_*
python migrate.py fresh
python migrate.py status
```

`fresh` membuat ulang seluruh tabel aplikasi dan ledger migrasi dalam satu transaksi; jika gagal,
perubahan dibatalkan. Perintah ini tidak diperlukan pada instalasi Docker baru
dan tidak dijalankan saat aplikasi mulai atau restart.

Perbedaan dari skema lama yang telah disesuaikan:

- `data_pengiriman.nosi`: `VARCHAR(100)`, boleh kosong.
- Enam kolom `dataset`: `total_awal`, `eliminasi_wilayah`, `eliminasi_kosong`,
  `eliminasi_duplikat`, `eliminasi_alamat_umum`, `total_eliminasi`;
  semuanya `INTEGER NOT NULL DEFAULT 0`.

Data historis dalam dump tidak dimasukkan ke database baru.

Setup database PostgreSQL terisolasi berbasis Docker untuk sistem **GeoKurir Malang**, dengan skema yang diimplementasikan secara presisi sesuai dengan [Class Diagram](file:///home/rahmat/Documents/doly/classdiagram.png).

---

## 🏗️ Arsitektur & Layanan Docker

Compose menggunakan proyek `geokurir-actual`, termasuk web Flask di localhost:5001.
Layanan database:
1. **`postgres`** (PostgreSQL 16 Alpine):
   * Port host localhost `5433`; port dalam jaringan container `5432`.
   * Skema otomatis dieksekusi saat inisialisasi pertama via `/docker-entrypoint-initdb.d`.
   * Volume persisten `geokurir-actual_postgres_data`, terpisah dari deployment lain.
   * Healthcheck otomatis menggunakan `pg_isready`.
2. **`adminer`** (Adminer Database GUI):
   * Port localhost `8081` (akses `http://127.0.0.1:8081`).
   * Antarmuka visual ringan untuk mengelola, query, dan melihat data PostgreSQL

---

## 📋 Detail Skema Tabel (Berdasarkan Class Diagram)

| No | Nama Tabel | Deskripsi & Relasi |
| :--- | :--- | :--- |
| 1 | **`dataset`** | Metadata file kiriman harian (`id_dataset`, `nama_file`, `tanggal_data`, `jumlah_data`, `jumlah_kurir`, `status`, `created_at`). |
| 2 | **`data_pengiriman`** | Titik pengiriman per dataset, termasuk `nosi`, `petugas` opsional, alamat, koordinat geografis/meter, dan status geocoding. |
| 3 | **`hasil_clustering`** | Sesi K-Means, K manual, metrik seluruh titik, waktu komputasi, serta `evaluasi_perbandingan` JSONB untuk metrik pada subset yang sama dengan aktual. |
| 4 | **`cluster`** | Kelompok cluster K-Means (`id_cluster`, `id_clustering`, `nomor_cluster`, `centroid_x`, `centroid_y`, `jumlah_anggota`). Relasi: `hasil_clustering` (1) $\rightarrow$ (*) `cluster`. |
| 5 | **`anggota_cluster`** | Pemetaan titik ke cluster (`id_anggota`, `id_cluster`, `id_pengiriman`, `jarak_ke_centroid`). Relasi many-to-one ke `cluster` dan `data_pengiriman`. |
| 6 | **`hasil_optimasi`** | Hasil penyeimbangan kurir HBCDP (`id_optimasi`, `id_clustering`, `nilai_z1`, `nilai_z2`, `status`, `created_at`). Relasi: `hasil_clustering` (1) $\rightarrow$ (1) `hasil_optimasi`. |
| 7 | **`zona_kurir`** | Poligon Convex Hull wilayah kerja kurir (`id_zona`, `id_optimasi`, `nomor_zona`, `jumlah_anggota`, `polygon`). Relasi: `hasil_optimasi` (1) $\rightarrow$ (*) `zona_kurir`. |
| 8 | **`history_proses`** | Audit trail log riwayat sistem (`id_history`, `id_dataset`, `id_clustering`, `id_optimasi`, `jenis_proses`, `status`, `created_at`). |
| 9 | **`evaluasi_aktual`** | Satu baseline terkini per `id_dataset` (UNIQUE, FK ON DELETE CASCADE), dihitung setelah geocoding dan sebelum clustering. |
| 10 | **`schema_migrations`** | Versi SQL tambahan beserta waktu penerapannya; metadata migrasi. |

### Baseline aktual

Kolom `evaluasi_aktual`: `id_evaluasi`, `id_dataset`, `jumlah_titik_geocoding`,
`jumlah_titik_evaluasi`, `jumlah_kurir_aktual`, `silhouette_score`, `dbi`, `z1`,
`status_evaluasi`, `alasan_na`, `distribusi` (JSONB), `sidik_data` (SHA-256),
dan `dihitung_pada` (TIMESTAMPTZ).

Nilai tidak terdefinisi disimpan sebagai NULL dan tampil N/A. Status membedakan
`tersedia`, `sebagian`, dan `tidak_tersedia`. Petugas kosong tidak menghalangi
clustering. Distribusi dan metrik aktual hanya memakai Petugas terisi pada titik
SUCCESS; K tidak disimpan sebagai parameter baseline.

Sidik data mencakup seluruh titik SUCCESS dan Petugasnya. Endpoint clustering
menolak baseline yang belum dihitung atau kedaluwarsa, tanpa menghitung ulang
aktual. Jalankan geocoding lagi jika titik/Petugas berubah. K yang berubah
memakai baseline tersimpan. `evaluasi_perbandingan` menyimpan sidik data dan
metrik algoritma pada resi ber-Petugas yang sama; Z₂ dan tahap HBCDP tetap
diagnostik seluruh titik.


---

## 🔑 Kredensial & Konfigurasi Koneksi

Konfigurasi disimpan pada file [`.env`](file:///home/rahmat/Documents/doly/.env):

```env
DB_HOST=localhost
DB_PORT=5433
DB_USER=geokurir
DB_PASSWORD=geokurir_secret
DB_NAME=geokurir_db
ADMINER_PORT=8081
```

### Connection String:
```text
postgresql://geokurir:geokurir_secret@localhost:5433/geokurir_db
```

---

## 🚀 Perintah Manajemen Docker

### Menjalankan Container:
```bash
docker compose up -d
```

### Memeriksa Status Container:
```bash
docker compose ps
```

### Membuka PostgreSQL CLI (`psql`):
```bash
docker compose exec postgres psql -U geokurir -d geokurir_db
```

### Menghentikan Container:
```bash
docker compose down
```

### Reset Total Database (Hapus data volume):
```bash
docker compose down -v
docker compose up -d
```

---

## 🌐 Akses Web GUI (Adminer)

Buka browser ke `http://127.0.0.1:8081` dan masukkan kredensial:
* **System**: `PostgreSQL`
* **Server**: `postgres`
* **Username**: `geokurir`
* **Password**: `geokurir_secret`
* **Database**: `geokurir_db`
