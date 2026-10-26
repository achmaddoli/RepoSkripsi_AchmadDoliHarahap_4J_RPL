# Setup Database PostgreSQL dengan Docker — GeoKurir Malang

## Database baru dimulai kosong

`database/01_schema.sql` berisi struktur delapan tabel yang sesuai
`geokurir_db.sql`, tanpa data pengiriman. Docker Compose hanya menjalankan
skema ini pada volume PostgreSQL baru. File dump tidak diperlukan pada
perangkat baru atau server publik dan tidak diimpor secara otomatis.

- Instalasi baru dengan volume baru: semua tabel kosong, ID dimulai dari 1.
- Restart/deploy ulang dengan volume yang sama: data tetap tersimpan.
- Pindah perangkat: salin kode dan buat `.env` baru; jangan pindahkan volume
  PostgreSQL atau memulihkan dump jika ingin mulai kosong.

Dashboard kosong menampilkan ajakan mengunggah dataset. `02_seed.sql` dan
`seed_dataset1.py` adalah contoh lama yang tidak dijalankan otomatis.

### Memeriksa atau mereset database yang sudah ada

`python migrate.py` dan `python migrate.py status` hanya memeriksa jumlah data.
Reset manual **menghapus semua data**. Jika memang ingin mengosongkan database
yang sudah ada, cadangkan dahulu, lalu gunakan perintah berikut dari lingkungan
Python yang sudah dipasangi dependensi:

```bash
# Simpan cadangan di luar folder website (misalnya direktori pribadi).
docker exec geokurir-postgres pg_dump -U geokurir -d geokurir_db > /tmp/geokurir-before-restore.sql

# Menghapus data dan membuat ulang skema kosong menggunakan konfigurasi DB_*
python migrate.py fresh
python migrate.py status
```

`fresh` membuat ulang seluruh delapan tabel dalam satu transaksi; jika gagal,
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

Konfigurasi menggunakan **Docker Compose** dengan dua container:
1. **`geokurir-postgres`** (PostgreSQL 16 Alpine):
   * Port: `5432`
   * Skema otomatis dieksekusi saat inisialisasi pertama via `/docker-entrypoint-initdb.d`
   * Penyimpanan persisten volume `postgres_data`
   * Healthcheck otomatis menggunakan `pg_isready`
2. **`geokurir-adminer`** (Adminer Database GUI):
   * Port: `8080` (Akses web browser di `http://localhost:8080`)
   * Antarmuka visual ringan untuk mengelola, query, dan melihat data PostgreSQL

---

## 📋 Detail Skema Tabel (Berdasarkan Class Diagram)

| No | Nama Tabel | Deskripsi & Relasi |
| :--- | :--- | :--- |
| 1 | **`dataset`** | Metadata file kiriman harian (`id_dataset`, `nama_file`, `tanggal_data`, `jumlah_data`, `jumlah_kurir`, `status`, `created_at`). |
| 2 | **`data_pengiriman`** | Data tiap titik alamat (`id_pengiriman`, `id_dataset`, `alamat_asli`, `alamat_bersih`, `latitude`, `longitude`, `x_meter`, `y_meter`, `status_geocoding`). Relasi: `dataset` (1) $\rightarrow$ (*) `data_pengiriman`. |
| 3 | **`hasil_clustering`** | Hasil K-Means awal (`id_clustering`, `id_dataset`, `jumlah_cluster`, `silhouette_score`, `dbi`, `created_at`). Relasi: `dataset` (1) $\rightarrow$ (*) `hasil_clustering`. |
| 4 | **`cluster`** | Kelompok cluster K-Means (`id_cluster`, `id_clustering`, `nomor_cluster`, `centroid_x`, `centroid_y`, `jumlah_anggota`). Relasi: `hasil_clustering` (1) $\rightarrow$ (*) `cluster`. |
| 5 | **`anggota_cluster`** | Pemetaan titik ke cluster (`id_anggota`, `id_cluster`, `id_pengiriman`, `jarak_ke_centroid`). Relasi many-to-one ke `cluster` dan `data_pengiriman`. |
| 6 | **`hasil_optimasi`** | Hasil penyeimbangan kurir HBCDP (`id_optimasi`, `id_clustering`, `nilai_z1`, `nilai_z2`, `status`, `created_at`). Relasi: `hasil_clustering` (1) $\rightarrow$ (1) `hasil_optimasi`. |
| 7 | **`zona_kurir`** | Poligon Convex Hull wilayah kerja kurir (`id_zona`, `id_optimasi`, `nomor_zona`, `jumlah_anggota`, `polygon`). Relasi: `hasil_optimasi` (1) $\rightarrow$ (*) `zona_kurir`. |
| 8 | **`history_proses`** | Audit trail log riwayat sistem (`id_history`, `id_dataset`, `id_clustering`, `id_optimasi`, `jenis_proses`, `status`, `created_at`). |

---

## 🔑 Kredensial & Konfigurasi Koneksi

Konfigurasi disimpan pada file [`.env`](file:///home/rahmat/Documents/doly/.env):

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=geokurir
DB_PASSWORD=geokurir_secret
DB_NAME=geokurir_db
ADMINER_PORT=8080
```

### Connection String:
```text
postgresql://geokurir:geokurir_secret@localhost:5432/geokurir_db
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
docker exec -it geokurir-postgres psql -U geokurir -d geokurir_db
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

Buka browser ke `http://localhost:8080` dan masukkan kredensial:
* **System**: `PostgreSQL`
* **Server**: `postgres`
* **Username**: `geokurir`
* **Password**: `geokurir_secret`
* **Database**: `geokurir_db`
