
import unittest
from unittest.mock import patch, Mock
import requests

from services.geocoding_service import GeocodingService


class TestGeocodingGagal(unittest.TestCase):

    def setUp(self):
        self.service = GeocodingService(api_key="API_KEY_DUMMY")
        self.alamat = "Jl. Ijen No. 10, Malang"

    def mock_api(self, data, http_status=200):
        response = Mock()
        response.status_code = http_status
        response.raise_for_status.return_value = None
        response.json.return_value = data
        return response

    def cek_gagal(self, hasil, pesan):
        self.assertEqual(hasil["status"], "FAILED")
        self.assertIn(pesan, hasil["error"])
        for kolom in ("latitude", "longitude", "x_meter", "y_meter"):
            self.assertIsNone(hasil[kolom])

    def test_01_alamat_kosong(self):
        hasil = self.service.geocode("")
        self.cek_gagal(hasil, "Alamat kosong")

    def test_02_api_key_kosong(self):
        service = GeocodingService(api_key="")
        hasil = service.geocode(self.alamat)
        self.cek_gagal(hasil, "API Key belum tersedia")

    def cek_status_api(self, status, pesan):
        with patch("services.geocoding_service.requests.get") as mock_get:
            mock_get.return_value = self.mock_api({
                "status": status,
                "results": []
            })
            hasil = self.service.geocode(self.alamat)
            self.cek_gagal(hasil, pesan)
            mock_get.assert_called_once()

    def test_03_zero_results(self):
        self.cek_status_api(
            "ZERO_RESULTS", "Alamat tidak ditemukan"
        )

    def test_04_over_query_limit(self):
        self.cek_status_api(
            "OVER_QUERY_LIMIT", "Batas permintaan"
        )

    def test_05_over_daily_limit(self):
        self.cek_status_api(
            "OVER_DAILY_LIMIT", "Batas penggunaan"
        )

    def test_06_request_denied(self):
        self.cek_status_api(
            "REQUEST_DENIED", "Permintaan ditolak"
        )

    def test_07_invalid_request(self):
        self.cek_status_api(
            "INVALID_REQUEST", "Parameter geocoding"
        )

    def test_08_unknown_error(self):
        self.cek_status_api(
            "UNKNOWN_ERROR", "gangguan sementara"
        )

    def test_09_results_kosong(self):
        with patch("services.geocoding_service.requests.get") as mock_get:
            mock_get.return_value = self.mock_api({
                "status": "OK",
                "results": []
            })
            hasil = self.service.geocode(self.alamat)
            self.cek_gagal(
                hasil, "tidak mengembalikan koordinat"
            )

    def test_10_di_luar_kota_malang(self):
        with patch("services.geocoding_service.requests.get") as mock_get:
            mock_get.return_value = self.mock_api({
                "status": "OK",
                "results": [{
                    "address_components": [{
                        "long_name": "Kota Surabaya",
                        "types": ["administrative_area_level_2"]
                    }],
                    "geometry": {
                        "location": {
                            "lat": -7.2575,
                            "lng": 112.7521
                        }
                    }
                }]
            })
            hasil = self.service.geocode(self.alamat)
            self.cek_gagal(
                hasil, "di luar Kota Malang"
            )

    def test_11_timeout(self):
        with patch("services.geocoding_service.requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout(
                "Simulasi timeout"
            )
            hasil = self.service.geocode(self.alamat)
            self.cek_gagal(
                hasil, "Gagal menghubungi Google Maps"
            )

    def test_12_respons_tidak_valid(self):
        with patch("services.geocoding_service.requests.get") as mock_get:
            mock_get.return_value = self.mock_api({
                "status": "OK",
                "results": [{
                    "address_components": [{
                        "long_name": "Kota Malang",
                        "types": ["administrative_area_level_2"]
                    }],
                    "geometry": {
                        "location": {
                            "lat": "BUKAN_ANGKA",
                            "lng": 112.6326
                        }
                    }
                }]
            })
            hasil = self.service.geocode(self.alamat)
            self.cek_gagal(
                hasil, "Respons geocoding tidak valid"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
