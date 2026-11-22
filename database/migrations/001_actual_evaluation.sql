-- Additive and repeat-safe: retain existing datasets, points, and cluster results.
ALTER TABLE data_pengiriman ADD COLUMN IF NOT EXISTS petugas TEXT;
ALTER TABLE hasil_clustering ADD COLUMN IF NOT EXISTS evaluasi_perbandingan JSONB;

CREATE TABLE IF NOT EXISTS evaluasi_aktual (
    id_evaluasi SERIAL PRIMARY KEY,
    id_dataset INTEGER NOT NULL UNIQUE REFERENCES dataset(id_dataset) ON DELETE CASCADE,
    jumlah_titik_geocoding INTEGER NOT NULL CHECK (jumlah_titik_geocoding >= 0),
    jumlah_titik_evaluasi INTEGER NOT NULL CHECK (
        jumlah_titik_evaluasi >= 0 AND jumlah_titik_evaluasi <= jumlah_titik_geocoding
    ),
    jumlah_kurir_aktual INTEGER CHECK (
        jumlah_kurir_aktual >= 1 AND jumlah_kurir_aktual <= jumlah_titik_evaluasi
    ),
    silhouette_score DOUBLE PRECISION CHECK (silhouette_score BETWEEN -1 AND 1),
    dbi DOUBLE PRECISION CHECK (dbi >= 0 AND dbi < 'Infinity'::DOUBLE PRECISION),
    z1 DOUBLE PRECISION CHECK (z1 >= 0 AND z1 < 'Infinity'::DOUBLE PRECISION),
    status_evaluasi TEXT NOT NULL CHECK (
        status_evaluasi IN ('tersedia', 'sebagian', 'tidak_tersedia')
    ),
    alasan_na TEXT,
    distribusi JSONB NOT NULL DEFAULT '[]'::JSONB CHECK (jsonb_typeof(distribusi) = 'array'),
    sidik_data TEXT NOT NULL CHECK (length(sidik_data) = 64),
    dihitung_pada TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT evaluasi_aktual_jumlah_kurir CHECK (
        (jumlah_titik_evaluasi = 0 AND jumlah_kurir_aktual IS NULL)
        OR (jumlah_titik_evaluasi > 0 AND jumlah_kurir_aktual IS NOT NULL)
    ),
    CONSTRAINT evaluasi_aktual_ketersediaan CHECK (
        (status_evaluasi = 'tersedia'
            AND silhouette_score IS NOT NULL AND dbi IS NOT NULL AND z1 IS NOT NULL
            AND alasan_na IS NULL)
        OR (status_evaluasi = 'sebagian'
            AND (silhouette_score IS NOT NULL OR dbi IS NOT NULL OR z1 IS NOT NULL)
            AND (silhouette_score IS NULL OR dbi IS NULL OR z1 IS NULL)
            AND alasan_na IS NOT NULL)
        OR (status_evaluasi = 'tidak_tersedia'
            AND silhouette_score IS NULL AND dbi IS NULL AND z1 IS NULL
            AND alasan_na IS NOT NULL)
    )
);

COMMENT ON COLUMN data_pengiriman.petugas IS 'Petugas PT Pos opsional, dipertahankan dari resi asal';
COMMENT ON COLUMN hasil_clustering.evaluasi_perbandingan IS 'Metrik K-Means dan HBCDP pada subset Petugas valid yang sama; tanpa clustering ulang';
COMMENT ON TABLE evaluasi_aktual IS 'Baseline penugasan aktual setelah geocoding, satu versi terkini per dataset';
COMMENT ON COLUMN evaluasi_aktual.sidik_data IS 'SHA-256 seluruh titik berhasil geocoding untuk mendeteksi baseline kedaluwarsa';
COMMENT ON COLUMN evaluasi_aktual.z1 IS 'Variansi populasi jumlah titik per Petugas aktual; bukan simpangan baku';
