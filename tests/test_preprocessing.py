"""
Unit test untuk PreprocessingService (Revisi 29 Oktober)
Memverifikasi 4 tahapan preprocessing:
1. Pemeriksaan Data Kosong
2. Seleksi Wilayah
3. Pemeriksaan Resi Duplikat
4. Normalisasi Alamat
"""

import unittest
from services.preprocessing_service import PreprocessingService


class PreprocessingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = PreprocessingService()
        self.col_map = {
            "Nosi": "Nosi",
            "Tgl Antaran Pertama": "Tgl Antaran Pertama",
            "Alamat": "Alamat",
            "Kota": "Kota"
        }

    def test_normalisasi_alamat(self):
        """Memverifikasi standarisasi Jalan, Gang, Nomor, dan spasi."""
        cases = [
            ("JL. Ijen NO. 10", "Jalan Ijen No. 10"),
            ("JLN Soekarno Hatta NO 25", "Jalan Soekarno Hatta No. 25"),
            ("GG. Kelinci NOMOR 3", "Gang Kelinci No. 3"),
            ("Jalan   Merbabu    No.15", "Jalan Merbabu No. 15"),
            ("GG Mawar NO.7", "Gang Mawar No. 7"),
        ]
        for raw, expected in cases:
            cleaned = self.service.bersihkan_alamat(raw)
            self.assertEqual(cleaned, expected)

    def test_seleksi_wilayah_kota_malang(self):
        """Memverifikasi hanya wilayah Kota Malang dan kecamatannya yang valid."""
        self.assertTrue(self.service.is_valid_kota("MALANG"))
        self.assertTrue(self.service.is_valid_kota("KOTA MALANG"))
        self.assertTrue(self.service.is_valid_kota("MALANG, KLOJEN"))
        self.assertTrue(self.service.is_valid_kota("MALANG, BLIMBING, PURWODADI"))

        self.assertFalse(self.service.is_valid_kota("SURABAYA"))
        self.assertFalse(self.service.is_valid_kota("KABUPATEN MALANG"))
        self.assertFalse(self.service.is_valid_kota("KOTA BATU"))
        self.assertFalse(self.service.is_valid_kota(""))

    def test_pemeriksaan_data_kosong(self):
        """Data dengan resi atau alamat kosong harus masuk ke kategori data_kosong."""
        rows = [
            {"Nosi": "", "Alamat": "Jl. Ijen No. 1", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            {"Nosi": "001", "Alamat": "", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            {"Nosi": "002", "Alamat": "Jl. Ijen No. 2", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"}
        ]
        res = self.service.proses_dataset(rows, self.col_map)
        summary = res["summary"]
        self.assertEqual(summary["total_awal"], 3)
        self.assertEqual(summary["rincian"]["data_kosong"]["count"], 2)
        self.assertEqual(summary["total_valid"], 1)

    def test_pemeriksaan_resi_duplikat(self):
        """Resi berulang harus dieliminasi dan hanya disimpan satu kali."""
        rows = [
            {"Nosi": "RESI001", "Alamat": "Jl. Ijen No. 1", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            {"Nosi": "RESI001", "Alamat": "Jl. Ijen No. 1B", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            {"Nosi": "RESI002", "Alamat": "Jl. Ijen No. 2", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"}
        ]
        res = self.service.proses_dataset(rows, self.col_map)
        summary = res["summary"]
        self.assertEqual(summary["total_awal"], 3)
        self.assertEqual(summary["rincian"]["resi_duplikat"]["count"], 1)
        self.assertEqual(summary["total_valid"], 2)
        self.assertEqual(res["valid_rows"][0]["resi"], "RESI001")
        self.assertEqual(res["valid_rows"][1]["resi"], "RESI002")

    def test_urutan_lengkap_dan_konsistensi_jumlah(self):
        """Memverifikasi seluruh 4 tahapan berurutan dan total_awal == total_valid + total_eliminasi."""
        rows = [
            # 1. Kosong resi
            {"Nosi": "", "Alamat": "Jl. Ijen No. 1", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            # 2. Luar wilayah
            {"Nosi": "RESI002", "Alamat": "Jl. Pemuda No. 2", "Kota": "Surabaya", "Tgl Antaran Pertama": "01/08/2025"},
            # 3. Alamat terlalu umum
            {"Nosi": "RESI003", "Alamat": "KOTA MALANG", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            # 4. Valid 1
            {"Nosi": "RESI004", "Alamat": "JL. Borobudur NO 10", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            # 5. Duplikat dari RESI004
            {"Nosi": "RESI004", "Alamat": "Jl. Borobudur No. 10", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
            # 6. Valid 2
            {"Nosi": "RESI005", "Alamat": "GG. Melati NO.5", "Kota": "Malang", "Tgl Antaran Pertama": "01/08/2025"},
        ]
        res = self.service.proses_dataset(rows, self.col_map)
        summary = res["summary"]

        self.assertEqual(summary["total_awal"], 6)
        self.assertEqual(summary["rincian"]["data_kosong"]["count"], 1)
        self.assertEqual(summary["rincian"]["di_luar_wilayah"]["count"], 2)  # Surabaya & KOTA MALANG
        self.assertEqual(summary["rincian"]["resi_duplikat"]["count"], 1)  # RESI004 kedua
        self.assertEqual(summary["total_valid"], 2)

        # Invarian matematis: total_awal == total_valid + total_eliminasi
        self.assertEqual(summary["total_awal"], summary["total_valid"] + summary["total_eliminasi"])

        # Periksa hasil normalisasi alamat pada data valid
        valid_rows = res["valid_rows"]
        self.assertEqual(valid_rows[0]["alamat_bersih"], "Jalan Borobudur No. 10")
        self.assertEqual(valid_rows[1]["alamat_bersih"], "Gang Melati No. 5")


if __name__ == "__main__":
    unittest.main()
