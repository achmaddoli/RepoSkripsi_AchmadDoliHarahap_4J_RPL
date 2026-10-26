-- ============================================================================
-- GeoKurir Malang - Database Schema PostgreSQL
-- Berdasarkan Class Diagram Sistem Evaluasi Clustering (classdiagram.png)
-- ============================================================================

-- Bersihkan tabel yang ada sebelumnya (urutan reverse dependency)
DROP TABLE IF EXISTS history_proses CASCADE;
DROP TABLE IF EXISTS zona_kurir CASCADE;
DROP TABLE IF EXISTS hasil_optimasi CASCADE;
DROP TABLE IF EXISTS anggota_cluster CASCADE;
DROP TABLE IF EXISTS cluster CASCADE;
DROP TABLE IF EXISTS hasil_clustering CASCADE;
DROP TABLE IF EXISTS data_pengiriman CASCADE;
DROP TABLE IF EXISTS dataset CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Tabel: Dataset
-- Menyimpan informasi metadata file dataset harian pengiriman
-- ----------------------------------------------------------------------------
CREATE TABLE dataset (
    id_dataset SERIAL PRIMARY KEY,
    nama_file VARCHAR(255) NOT NULL,
    tanggal_data DATE NOT NULL,
    jumlah_data INT NOT NULL DEFAULT 0,
    jumlah_kurir INT NOT NULL DEFAULT 5,
    status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_awal INTEGER NOT NULL DEFAULT 0,
    eliminasi_wilayah INTEGER NOT NULL DEFAULT 0,
    eliminasi_kosong INTEGER NOT NULL DEFAULT 0,
    eliminasi_duplikat INTEGER NOT NULL DEFAULT 0,
    eliminasi_alamat_umum INTEGER NOT NULL DEFAULT 0,
    total_eliminasi INTEGER NOT NULL DEFAULT 0
);

COMMENT ON TABLE dataset IS 'Menyimpan metadata file dataset pengiriman per batch/tanggal';
COMMENT ON COLUMN dataset.id_dataset IS 'Primary key identitas unik dataset';
COMMENT ON COLUMN dataset.nama_file IS 'Nama file dataset yang diunggah (misal: 1 Agustus.csv)';
COMMENT ON COLUMN dataset.tanggal_data IS 'Tanggal pengantaran pertama dari paket pengiriman';
COMMENT ON COLUMN dataset.jumlah_data IS 'Total jumlah baris data pengiriman dalam dataset';
COMMENT ON COLUMN dataset.jumlah_kurir IS 'Jumlah kurir (K) yang dialokasikan untuk clustering';
COMMENT ON COLUMN dataset.status IS 'Status pemrosesan: UPLOADED, GEOCODING, PROCESSED, COMPLETED, ERROR';
COMMENT ON COLUMN dataset.created_at IS 'Waktu unggah dan pencatatan data ke sistem';

-- ----------------------------------------------------------------------------
-- 2. Tabel: DataPengiriman (Relasi: Dataset 1 -> * DataPengiriman)
-- Menyimpan data setiap resi/paket, alamat asli, hasil pembersihan & geocoding
-- ----------------------------------------------------------------------------
CREATE TABLE data_pengiriman (
    id_pengiriman SERIAL PRIMARY KEY,
    id_dataset INT NOT NULL REFERENCES dataset(id_dataset) ON DELETE CASCADE,
    alamat_asli TEXT NOT NULL,
    alamat_bersih TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    x_meter DOUBLE PRECISION,
    y_meter DOUBLE PRECISION,
    status_geocoding VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    nosi VARCHAR(100)
);

COMMENT ON TABLE data_pengiriman IS 'Data detail setiap titik alamat paket pengiriman dari dataset';
COMMENT ON COLUMN data_pengiriman.id_pengiriman IS 'Primary key identitas titik pengiriman';
COMMENT ON COLUMN data_pengiriman.id_dataset IS 'Foreign key ke tabel dataset';
COMMENT ON COLUMN data_pengiriman.alamat_asli IS 'Teks alamat awal yang tercatat pada resi/dokumen kirim';
COMMENT ON COLUMN data_pengiriman.alamat_bersih IS 'Teks alamat setelah proses preprocessing dan standardisasi';
COMMENT ON COLUMN data_pengiriman.latitude IS 'Koordinat lintang (derajat desimal WGS84)';
COMMENT ON COLUMN data_pengiriman.longitude IS 'Koordinat bujur (derajat desimal WGS84)';
COMMENT ON COLUMN data_pengiriman.x_meter IS 'Koordinat lokal East (meter) relatif terhadap origin KCU Pos Malang';
COMMENT ON COLUMN data_pengiriman.y_meter IS 'Koordinat lokal North (meter) relatif terhadap origin KCU Pos Malang';
COMMENT ON COLUMN data_pengiriman.status_geocoding IS 'Status proses geocoding: PENDING, SUCCESS, FAILED';

-- ----------------------------------------------------------------------------
-- 3. Tabel: HasilClustering (Relasi: Dataset 1 -> * HasilClustering)
-- Menyimpan hasil evaluasi dan metadata proses K-Means awal
-- ----------------------------------------------------------------------------
CREATE TABLE hasil_clustering (
    id_clustering SERIAL PRIMARY KEY,
    id_dataset INT NOT NULL REFERENCES dataset(id_dataset) ON DELETE CASCADE,
    jumlah_cluster INT NOT NULL,
    silhouette_score DOUBLE PRECISION,
    dbi DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE hasil_clustering IS 'Menyimpan hasil proses clustering K-Means awal beserta metrik evaluasinya';
COMMENT ON COLUMN hasil_clustering.id_clustering IS 'Primary key sesi clustering';
COMMENT ON COLUMN hasil_clustering.id_dataset IS 'Foreign key ke dataset yang diproses';
COMMENT ON COLUMN hasil_clustering.jumlah_cluster IS 'Jumlah cluster (K) yang terbentuk';
COMMENT ON COLUMN hasil_clustering.silhouette_score IS 'Skor evaluasi Silhouette Score K-Means awal';
COMMENT ON COLUMN hasil_clustering.dbi IS 'Skor evaluasi Davies-Bouldin Index (DBI) K-Means awal';
COMMENT ON COLUMN hasil_clustering.created_at IS 'Waktu eksekusi clustering';

-- ----------------------------------------------------------------------------
-- 4. Tabel: Cluster (Relasi: HasilClustering 1 -> * Cluster)
-- Menyimpan detail tiap kelompok zona/kurir pada hasil K-Means
-- ----------------------------------------------------------------------------
CREATE TABLE cluster (
    id_cluster SERIAL PRIMARY KEY,
    id_clustering INT NOT NULL REFERENCES hasil_clustering(id_clustering) ON DELETE CASCADE,
    nomor_cluster INT NOT NULL,
    centroid_x DOUBLE PRECISION,
    centroid_y DOUBLE PRECISION,
    jumlah_anggota INT NOT NULL DEFAULT 0
);

COMMENT ON TABLE cluster IS 'Data kelompok zona cluster hasil K-Means awal';
COMMENT ON COLUMN cluster.id_cluster IS 'Primary key identitas cluster';
COMMENT ON COLUMN cluster.id_clustering IS 'Foreign key ke sesi hasil clustering';
COMMENT ON COLUMN cluster.nomor_cluster IS 'Nomor urut cluster (1 s.d. K)';
COMMENT ON COLUMN cluster.centroid_x IS 'Titik pusat koordinat X (meter / bujur) centroid';
COMMENT ON COLUMN cluster.centroid_y IS 'Titik pusat koordinat Y (meter / lintang) centroid';
COMMENT ON COLUMN cluster.jumlah_anggota IS 'Jumlah titik pengiriman yang tergabung dalam cluster ini';

-- ----------------------------------------------------------------------------
-- 5. Tabel: AnggotaCluster (Relasi: Cluster 1 -> * Anggota, DataPengiriman 1 -> * Anggota)
-- Menyimpan asosiasi penugasan titik pengiriman ke suatu cluster
-- ----------------------------------------------------------------------------
CREATE TABLE anggota_cluster (
    id_anggota SERIAL PRIMARY KEY,
    id_cluster INT NOT NULL REFERENCES cluster(id_cluster) ON DELETE CASCADE,
    id_pengiriman INT NOT NULL REFERENCES data_pengiriman(id_pengiriman) ON DELETE CASCADE,
    jarak_ke_centroid DOUBLE PRECISION,
    nomor_zona INT,
    CONSTRAINT uq_cluster_pengiriman UNIQUE (id_cluster, id_pengiriman)
);

COMMENT ON TABLE anggota_cluster IS 'Menghubungkan titik pengiriman ke cluster penugasannya';
COMMENT ON COLUMN anggota_cluster.id_anggota IS 'Primary key asosiasi anggota cluster';
COMMENT ON COLUMN anggota_cluster.id_cluster IS 'Foreign key ke tabel cluster';
COMMENT ON COLUMN anggota_cluster.id_pengiriman IS 'Foreign key ke tabel data_pengiriman';
COMMENT ON COLUMN anggota_cluster.jarak_ke_centroid IS 'Jarak Euclidean dari titik pengiriman ke pusat centroid (meter)';
COMMENT ON COLUMN anggota_cluster.nomor_zona IS 'Nomor zona penugasan akhir hasil optimasi HBCDP';

-- ----------------------------------------------------------------------------
-- 6. Tabel: HasilOptimasi (Relasi: HasilClustering 1 -> 1 HasilOptimasi)
-- Menyimpan hasil optimasi dan penyeimbangan kurir menggunakan HBCDP
-- ----------------------------------------------------------------------------
CREATE TABLE hasil_optimasi (
    id_optimasi SERIAL PRIMARY KEY,
    id_clustering INT NOT NULL REFERENCES hasil_clustering(id_clustering) ON DELETE CASCADE,
    nilai_z1 DOUBLE PRECISION,
    nilai_z2 DOUBLE PRECISION,
    silhouette_score DOUBLE PRECISION,
    dbi DOUBLE PRECISION,
    steps_json TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_clustering_optimasi UNIQUE (id_clustering)
);

COMMENT ON TABLE hasil_optimasi IS 'Menyimpan hasil algoritma optimasi penyeimbangan beban kurir HBCDP';
COMMENT ON COLUMN hasil_optimasi.id_optimasi IS 'Primary key sesi optimasi';
COMMENT ON COLUMN hasil_optimasi.id_clustering IS 'Foreign key ke hasil clustering awal';
COMMENT ON COLUMN hasil_optimasi.nilai_z1 IS 'Nilai metrik variansi ukuran cluster (Z1 - penalti ketidakseimbangan)';
COMMENT ON COLUMN hasil_optimasi.nilai_z2 IS 'Nilai metrik jarak penalti (Z2 - total perpindahan jarak dalam meter)';
COMMENT ON COLUMN hasil_optimasi.status IS 'Status optimasi: SUCCESS, ITERATING, FAILED';
COMMENT ON COLUMN hasil_optimasi.created_at IS 'Waktu penyelesaian optimasi HBCDP';

-- ----------------------------------------------------------------------------
-- 7. Tabel: ZonaKurir (Relasi: HasilOptimasi 1 -> * ZonaKurir)
-- Menyimpan poligon Convex Hull dan wilayah kerja kurir hasil akhir
-- ----------------------------------------------------------------------------
CREATE TABLE zona_kurir (
    id_zona SERIAL PRIMARY KEY,
    id_optimasi INT NOT NULL REFERENCES hasil_optimasi(id_optimasi) ON DELETE CASCADE,
    nomor_zona INT NOT NULL,
    jumlah_anggota INT NOT NULL DEFAULT 0,
    polygon TEXT NOT NULL
);

COMMENT ON TABLE zona_kurir IS 'Data zona kerja kurir akhir dan batas poligon wilayah (Convex Hull)';
COMMENT ON COLUMN zona_kurir.id_zona IS 'Primary key zona kurir';
COMMENT ON COLUMN zona_kurir.id_optimasi IS 'Foreign key ke hasil optimasi HBCDP';
COMMENT ON COLUMN zona_kurir.nomor_zona IS 'Nomor urut zona pengantaran kurir (Zona 1..K)';
COMMENT ON COLUMN zona_kurir.jumlah_anggota IS 'Jumlah paket/titik final setelah penyeimbangan HBCDP';
COMMENT ON COLUMN zona_kurir.polygon IS 'Representasi geometri batas wilayah (GeoJSON string atau format WKT)';

-- ----------------------------------------------------------------------------
-- 8. Tabel: HistoryProses (Relasi pencatatan log riwayat aktivitas sistem)
-- ----------------------------------------------------------------------------
CREATE TABLE history_proses (
    id_history SERIAL PRIMARY KEY,
    id_dataset INT REFERENCES dataset(id_dataset) ON DELETE SET NULL,
    id_clustering INT REFERENCES hasil_clustering(id_clustering) ON DELETE SET NULL,
    id_optimasi INT REFERENCES hasil_optimasi(id_optimasi) ON DELETE SET NULL,
    jenis_proses VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE history_proses IS 'Log riwayat seluruh tahapan proses (upload, geocoding, clustering, optimasi)';
COMMENT ON COLUMN history_proses.id_history IS 'Primary key log aktivitas';
COMMENT ON COLUMN history_proses.id_dataset IS 'Foreign key ke dataset terkait (jika ada)';
COMMENT ON COLUMN history_proses.id_clustering IS 'Foreign key ke clustering terkait (jika ada)';
COMMENT ON COLUMN history_proses.id_optimasi IS 'Foreign key ke optimasi terkait (jika ada)';
COMMENT ON COLUMN history_proses.jenis_proses IS 'Jenis aksi: UPLOAD, GEOCODING, KMEANS_CLUSTERING, HBCDP_OPTIMIZATION';
COMMENT ON COLUMN history_proses.status IS 'Status eksekusi: START, PROGRESS, COMPLETED, FAILED';
COMMENT ON COLUMN history_proses.created_at IS 'Waktu pencatatan log';

-- ----------------------------------------------------------------------------
-- Indeks Performa untuk Relasi & Query Agregasi
-- ----------------------------------------------------------------------------
CREATE INDEX idx_data_pengiriman_dataset ON data_pengiriman(id_dataset);
CREATE INDEX idx_data_pengiriman_status ON data_pengiriman(status_geocoding);
CREATE INDEX idx_hasil_clustering_dataset ON hasil_clustering(id_dataset);
CREATE INDEX idx_cluster_clustering ON cluster(id_clustering);
CREATE INDEX idx_anggota_cluster_cluster ON anggota_cluster(id_cluster);
CREATE INDEX idx_anggota_cluster_pengiriman ON anggota_cluster(id_pengiriman);
CREATE INDEX idx_hasil_optimasi_clustering ON hasil_optimasi(id_clustering);
CREATE INDEX idx_zona_kurir_optimasi ON zona_kurir(id_optimasi);
CREATE INDEX idx_history_proses_dataset ON history_proses(id_dataset);
CREATE INDEX idx_history_proses_created_at ON history_proses(created_at);
