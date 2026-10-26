-- ============================================================================
-- GeoKurir Malang - Database Seed Data PostgreSQL
-- Data Awal Pengujian Sistem Berdasarkan Dataset Malang & Penelitian 2026
-- ============================================================================

-- 1. Insert Dataset
INSERT INTO dataset (id_dataset, nama_file, tanggal_data, jumlah_data, jumlah_kurir, status, created_at)
VALUES 
(1, '1 Agustus.csv', '2025-08-01', 8615, 5, 'COMPLETED', '2025-08-01 08:30:00+07'),
(2, '22 Titik Malang.csv', '2025-08-01', 22, 5, 'COMPLETED', '2025-08-01 09:00:00+07');

-- 2. Insert DataPengiriman (22 Titik Skenario Validasi Malang)
INSERT INTO data_pengiriman (id_pengiriman, id_dataset, alamat_asli, alamat_bersih, latitude, longitude, x_meter, y_meter, status_geocoding)
VALUES
(1, 2, 'JL GADANG NO 22 KLOJEN', 'Jl. Gadang No. 22, Klojen, Malang', -8.005489, 112.630092, -29.46, -2434.44, 'SUCCESS'),
(2, 2, 'JALAN MURIA IV NO 691-A RT 006 RW 004 KEL ORO ORO DOWO', 'Jl. Muria IV No. 691-A, Oro-oro Dowo, Klojen, Malang', -7.971297, 112.627063, -362.99, 1367.49, 'SUCCESS'),
(3, 2, 'Ruko Perumnas Jl Terusan Danau Kerinci No 21 Pakis', 'Ruko Perumnas, Jl. Terusan Danau Kerinci No. 21, Pakis, Malang', -7.975192, 112.661797, 3461.83, 934.38, 'SUCCESS'),
(4, 2, 'JL TELUK MANDAR TROMOL POS 5 ARJOSARI BLIMBING', 'Jl. Teluk Mandar No. 5, Arjosari, Blimbing, Malang', -7.985169, 112.613503, -1856.22, -174.94, 'SUCCESS'),
(5, 2, 'Jalan Raya Ki Ageng Gribig No 36 39 Lesanpuro Kedungkandang', 'Jl. Raya Ki Ageng Gribig No. 36-39, Lesanpuro, Kedungkandang, Malang', -7.990748, 112.650106, 2174.36, -795.30, 'SUCCESS'),
(6, 2, 'Jalan Ikan Belida I No 11 RT 4 RW 5 Kelurahan Polowijen Blimbing', 'Jl. Ikan Belida I No. 11, Polowijen, Blimbing, Malang', -7.984231, 112.613853, -1817.66, -70.66, 'SUCCESS'),
(7, 2, 'Jalan Gilimanuk No 85 Lowokwaru Lowokwaru', 'Jl. Gilimanuk No. 85, Lowokwaru, Lowokwaru, Malang', -7.957535, 112.625892, -491.95, 2897.84, 'SUCCESS'),
(8, 2, 'JL BANDULAN XI 281 RT 6 RW 1 SUKUN', 'Jl. Bandulan XI No. 281, Bandulan, Sukun, Malang', -7.986014, 112.610153, -2225.07, -268.90, 'SUCCESS'),
(9, 2, 'JL KIAGENG GRIBIG GG 14/SAWO RT 002 RW 004 KEL KOTALAMA', 'Jl. Ki Ageng Gribig Gg. 14, Kotalama, Klojen, Malang', -7.990748, 112.650106, 2174.36, -795.30, 'SUCCESS'),
(10, 2, 'JL SOEKARNO HATTA RT 10 RW 04 LOWOKWARU', 'Jl. Soekarno Hatta RT 10 RW 04, Lowokwaru, Malang', -7.997633, 112.612412, -1976.39, -1560.95, 'SUCCESS'),
(11, 2, 'BNI KCU MALANG BASUKI RAHMAT JL.JEND BASUKI RAHMAT 57-59', 'Jl. Jenderal Basuki Rahmat No. 57-59, Klojen, Malang', -7.978406, 112.629402, -105.45, 577.00, 'SUCCESS'),
(12, 2, 'Perum Bulan Terang Utama Kr 21 No 25 Kel Madyopuro Kedungkandang', 'Perum Bulan Terang Utama KR 21 No. 25, Madyopuro, Kedungkandang, Malang', -7.986127, 112.633937, 393.93, -281.55, 'SUCCESS'),
(13, 2, 'Ruko Wow Jalan Raya Sawojajar Blok Ny No 1 Kedungkandang', 'Jl. Raya Sawojajar Blok NY No. 1, Sawojajar, Kedungkandang, Malang', -7.990477, 112.628024, -257.18, -765.22, 'SUCCESS'),
(14, 2, 'JL KALIURANG NO 70 LOWOKWARU KEC LOWOKWARU', 'Jl. Kaliurang No. 70, Rampal Celaket, Klojen, Malang', -7.963284, 112.632696, 257.23, 2258.50, 'SUCCESS'),
(15, 2, 'JL IKAN TOMBRO TENGAH SAWAH NO 18 TANJUNG SEKAR LOWOKWARU', 'Jl. Ikan Tombro Tengah Sawah No. 18, Tunjungsekar, Lowokwaru, Malang', -7.979206, 112.620077, -1132.29, 488.08, 'SUCCESS'),
(16, 2, 'Jalan Aries Munandar Gang V No 793 Klojen', 'Jl. Aries Munandar Gg. V No. 793, Kiduldalem, Klojen, Malang', -7.982264, 112.636022, 623.48, 148.10, 'SUCCESS'),
(17, 2, 'JALAN ZAINUL ARIFIN NO 90 KLOJEN MALANG', 'Jl. Zainul Arifin No. 90, Sukoharjo, Klojen, Malang', -7.983912, 112.634098, 411.70, -35.25, 'SUCCESS'),
(18, 2, 'JL KAUMAN IV B 641 3.3 KLOJEN', 'Jl. Kauman IV-B No. 641, Kauman, Klojen, Malang', -7.982693, 112.627714, -291.36, 100.36, 'SUCCESS'),
(19, 2, 'KANTOR HUKUM GUNTUR PUTRA & PARTNERS JL SAWOJAJAR KEDUNGKANDANG', 'Jl. Sawojajar No. 12, Sawojajar, Kedungkandang, Malang', -7.977244, 112.654598, 2669.09, 706.20, 'SUCCESS'),
(20, 2, 'Jl Kauman No 21 Kauman Klojen Vauza Tamma Umrah', 'Jl. Kauman No. 21, Kauman, Klojen, Malang', -7.982693, 112.627714, -291.36, 100.36, 'SUCCESS'),
(21, 2, 'JL KEBUN JERUK 15 KLOJEN', 'Jl. Kebun Jeruk No. 15, Klojen, Malang', -7.954532, 112.619265, -1221.66, 3231.69, 'SUCCESS'),
(22, 2, 'Jalan La Sucipto Gang Makam RT 3 RW 3 Pandanwangi Blimbing', 'Jl. L.A. Sucipto Gg. Makam RT 3 RW 3, Pandanwangi, Blimbing, Malang', -7.953797, 112.660160, 3281.55, 3313.41, 'SUCCESS');

-- 3. Insert HasilClustering
INSERT INTO hasil_clustering (id_clustering, id_dataset, jumlah_cluster, silhouette_score, dbi, created_at)
VALUES 
(1, 2, 5, 0.437741, 0.606318, '2025-08-01 09:15:00+07'),
(2, 1, 5, 0.442100, 0.621300, '2025-08-01 09:20:00+07');

-- 4. Insert Cluster K-Means Awal
INSERT INTO cluster (id_cluster, id_clustering, nomor_cluster, centroid_x, centroid_y, jumlah_anggota)
VALUES 
-- Untuk id_clustering = 1 (22 Titik)
(1, 1, 1, 2619.91, 14.99, 4),
(2, 1, 2, -1801.53, -417.09, 5),
(3, 1, 3, -454.84, 2438.88, 4),
(4, 1, 4, 82.72, -439.18, 8),
(5, 1, 5, 3281.55, 3313.41, 1),
-- Untuk id_clustering = 2 (8.615 Titik)
(6, 2, 1, 2400.50, 350.20, 1845),
(7, 2, 2, -1650.30, -420.50, 2120),
(8, 2, 3, -520.10, 2310.80, 1450),
(9, 2, 4, 110.40, -480.20, 2300),
(10, 2, 5, 3100.80, 3200.40, 900);

-- 5. Insert AnggotaCluster K-Means Awal & Penugasan Zona Akhir
INSERT INTO anggota_cluster (id_cluster, id_pengiriman, jarak_ke_centroid, nomor_zona)
VALUES 
-- Cluster 1 (4 anggota: A3, A5, A9, A19)
(1, 3, 1245.32, 5),
(1, 5, 915.20, 1),
(1, 9, 915.20, 1),
(1, 19, 693.41, 1),
-- Cluster 2 (5 anggota: A4, A6, A8, A10, A15)
(2, 4, 248.55, 2),
(2, 6, 346.88, 2),
(2, 8, 448.91, 2),
(2, 10, 1157.20, 2),
(2, 15, 1123.64, 2),
-- Cluster 3 (4 anggota: A2, A7, A14, A21)
(3, 2, 1075.31, 3),
(3, 7, 460.92, 3),
(3, 14, 734.48, 5),
(3, 21, 1095.82, 3),
-- Cluster 4 (8 anggota: A1, A11, A12, A13, A16, A17, A18, A20)
(4, 1, 2000.12, 4),
(4, 11, 1033.40, 3),
(4, 12, 349.52, 1),
(4, 13, 470.21, 4),
(4, 16, 796.88, 5),
(4, 17, 521.14, 4),
(4, 18, 655.20, 4),
(4, 20, 655.20, 4),
-- Cluster 5 (1 anggota: A22)
(5, 22, 0.00, 5);

-- 6. Insert HasilOptimasi HBCDP
INSERT INTO hasil_optimasi (id_optimasi, id_clustering, nilai_z1, nilai_z2, silhouette_score, dbi, steps_json, status, created_at)
VALUES 
(1, 1, 0.24, 12406.65, 0.1919, 1.1921, '[{"step": "Step 1", "nama": "Direct Reassignment", "cardinality": "[4, 5, 4, 5, 4]", "z1": "0.24", "z2": "13.804,97 m", "reassigned": 6}, {"step": "Step 2", "nama": "Path Reassignment (BFS)", "cardinality": "[4, 5, 4, 5, 4]", "z1": "0.24", "z2": "13.804,97 m", "reassigned": 0}, {"step": "Step 3", "nama": "Pairwise Exchange", "cardinality": "[4, 5, 4, 5, 4]", "z1": "0.24", "z2": "12.959,77 m", "reassigned": 4}, {"step": "Step 4", "nama": "Multiple Exchange (Bellman-Ford)", "cardinality": "[4, 5, 4, 5, 4]", "z1": "0.24", "z2": "12.406,65 m", "reassigned": 4}]', 'SUCCESS', '2025-08-01 09:18:00+07'),
(2, 2, 1.20, 14250.80, 0.2150, 1.1850, '[{"step": "Step 1", "nama": "Direct Reassignment", "cardinality": "[1720, 1726, 1721, 1724, 1724]", "z1": "4.80", "z2": "16.340,50 m", "reassigned": 580}, {"step": "Step 2", "nama": "Path Reassignment (BFS)", "cardinality": "[1720, 1726, 1721, 1724, 1724]", "z1": "4.80", "z2": "16.340,50 m", "reassigned": 0}, {"step": "Step 3", "nama": "Pairwise Exchange", "cardinality": "[1722, 1725, 1722, 1723, 1723]", "z1": "1.60", "z2": "15.120,20 m", "reassigned": 12}, {"step": "Step 4", "nama": "Multiple Exchange (Bellman-Ford)", "cardinality": "[1723, 1725, 1722, 1723, 1722]", "z1": "1.20", "z2": "14.250,80 m", "reassigned": 8}]', 'SUCCESS', '2025-08-01 09:25:00+07');

-- 7. Insert ZonaKurir
INSERT INTO zona_kurir (id_zona, id_optimasi, nomor_zona, jumlah_anggota, polygon)
VALUES 
-- Untuk id_optimasi = 1 (22 Titik)
(1, 1, 1, 4, '{"type":"Polygon","coordinates":[[[112.633937,-7.986127],[112.650106,-7.990748],[112.654598,-7.977244],[112.633937,-7.986127]]]}'),
(2, 1, 2, 5, '{"type":"Polygon","coordinates":[[[112.610153,-7.986014],[112.612412,-7.997633],[112.613853,-7.984231],[112.620077,-7.979206],[112.610153,-7.986014]]]}'),
(3, 1, 3, 4, '{"type":"Polygon","coordinates":[[[112.619265,-7.954532],[112.625892,-7.957535],[112.627063,-7.971297],[112.629402,-7.978406],[112.619265,-7.954532]]]}'),
(4, 1, 4, 5, '{"type":"Polygon","coordinates":[[[112.627714,-7.982693],[112.628024,-7.990477],[112.630092,-8.005489],[112.634098,-7.983912],[112.627714,-7.982693]]]}'),
(5, 1, 5, 4, '{"type":"Polygon","coordinates":[[[112.632696,-7.963284],[112.636022,-7.982264],[112.660160,-7.953797],[112.661797,-7.975192],[112.632696,-7.963284]]]}'),
-- Untuk id_optimasi = 2 (8.615 Titik)
(6, 2, 1, 1723, '{"type":"Polygon","coordinates":[[[112.633937,-7.986127],[112.650106,-7.990748],[112.654598,-7.977244],[112.633937,-7.986127]]]}'),
(7, 2, 2, 1725, '{"type":"Polygon","coordinates":[[[112.610153,-7.986014],[112.612412,-7.997633],[112.613853,-7.984231],[112.620077,-7.979206],[112.610153,-7.986014]]]}'),
(8, 2, 3, 1722, '{"type":"Polygon","coordinates":[[[112.619265,-7.954532],[112.625892,-7.957535],[112.627063,-7.971297],[112.629402,-7.978406],[112.619265,-7.954532]]]}'),
(9, 2, 4, 1723, '{"type":"Polygon","coordinates":[[[112.627714,-7.982693],[112.628024,-7.990477],[112.630092,-8.005489],[112.634098,-7.983912],[112.627714,-7.982693]]]}'),
(10, 2, 5, 1722, '{"type":"Polygon","coordinates":[[[112.632696,-7.963284],[112.636022,-7.982264],[112.660160,-7.953797],[112.661797,-7.975192],[112.632696,-7.963284]]]}');

-- 8. Insert HistoryProses
INSERT INTO history_proses (id_history, id_dataset, id_clustering, id_optimasi, jenis_proses, status, created_at)
VALUES 
(1, 2, NULL, NULL, 'UPLOAD', 'COMPLETED', '2025-08-01 09:00:00+07'),
(2, 2, NULL, NULL, 'GEOCODING', 'COMPLETED', '2025-08-01 09:05:00+07'),
(3, 2, 1, NULL, 'KMEANS_CLUSTERING', 'COMPLETED', '2025-08-01 09:15:00+07'),
(4, 2, 1, 1, 'HBCDP_OPTIMIZATION', 'COMPLETED', '2025-08-01 09:18:00+07'),
(5, 1, NULL, NULL, 'UPLOAD', 'COMPLETED', '2025-08-01 08:30:00+07'),
(6, 1, NULL, NULL, 'GEOCODING', 'COMPLETED', '2025-08-01 08:45:00+07'),
(7, 1, 2, NULL, 'KMEANS_CLUSTERING', 'COMPLETED', '2025-08-01 09:20:00+07'),
(8, 1, 2, 2, 'HBCDP_OPTIMIZATION', 'COMPLETED', '2025-08-01 09:25:00+07');

-- Sinkronkan urutan serial auto-increment PostgreSQL
SELECT setval('dataset_id_dataset_seq', (SELECT MAX(id_dataset) FROM dataset));
SELECT setval('data_pengiriman_id_pengiriman_seq', (SELECT MAX(id_pengiriman) FROM data_pengiriman));
SELECT setval('hasil_clustering_id_clustering_seq', (SELECT MAX(id_clustering) FROM hasil_clustering));
SELECT setval('cluster_id_cluster_seq', (SELECT MAX(id_cluster) FROM cluster));
SELECT setval('anggota_cluster_id_anggota_seq', (SELECT MAX(id_anggota) FROM anggota_cluster));
SELECT setval('hasil_optimasi_id_optimasi_seq', (SELECT MAX(id_optimasi) FROM hasil_optimasi));
SELECT setval('zona_kurir_id_zona_seq', (SELECT MAX(id_zona) FROM zona_kurir));
SELECT setval('history_proses_id_history_seq', (SELECT MAX(id_history) FROM history_proses));
