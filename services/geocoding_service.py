import math
import re
import requests
from config import Config

class GeocodingService:
    """
    GeocodingService berdasarkan Class Diagram
    Menangani validasi lokasi, pembersihan alamat, geocoding koordinat,
    dan transformasi koordinat ke meter lokal relatif terhadap KCU Pos Malang.
    """
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self.origin_lat = Config.KCU_ORIGIN_LAT
        self.origin_lon = Config.KCU_ORIGIN_LON
        self.earth_radius = 6371000.0  # Meter

        # 5 Kecamatan resmi di Kota Malang
        self.kecamatan_malang = [
            "KLOJEN", "BLIMBING", "LOWOKWARU", "SUKUN", "KEDUNGKANDANG"
        ]

    def validasiLokasi(self, alamat: str, kota: str = "MALANG") -> bool:
        """Memvalidasi apakah alamat berada dalam cakupan wilayah Kota Malang."""
        text = f"{alamat} {kota}".upper()
        if "MALANG" not in text:
            return False
        # Cek apakah setidaknya menyebut Malang atau salah satu kecamatan/kelurahan di Malang
        return True


    def isAlamatTerlaluUmum(self, alamat: str) -> bool:
        """
        Memeriksa apakah alamat hanya berisi wilayah administratif.

        True  = alamat terlalu umum, dieliminasi.
        False = alamat dipertahankan.
        """
        if alamat is None or not str(alamat).strip():
            return True

        teks = re.sub(r"\s+", " ", str(alamat).strip().upper())
        teks = teks.strip(" ,.;")

        if not teks:
            return True

        wilayah_umum = {
            "MALANG",
            "KOTA MALANG",
            "KABUPATEN MALANG",
            "JAWA TIMUR",
            *self.kecamatan_malang
        }

        def normalisasi_wilayah(bagian):
            bagian = bagian.strip(" .;")
            bagian = re.sub(
                r"^(?:KECAMATAN|KEC\.?|KELURAHAN|KEL\.?)\s+",
                "",
                bagian
            )
            return bagian.strip()

        bagian_alamat = [
            normalisasi_wilayah(p)
            for p in teks.split(",")
            if p.strip(" .;")
        ]

        # Eliminasi jika seluruh bagian alamat
        # hanya berisi wilayah administratif yang dikenali.
        if bagian_alamat and all(
            p in wilayah_umum for p in bagian_alamat
        ):
            return True

        # Alamat lainnya dipertahankan.
        return False


    def bersihkanAlamat(self, alamat: str) -> str:
        """Membersihkan spasi, singkatan jalan, gang, dan nomor."""
        if not alamat:
            return ""

        teks = re.sub(r"\s+", " ", str(alamat).strip())

        # Normalisasi singkatan jalan
        teks = re.sub(
            r"\b(?:JL|JLN|JALAN)\.?(?=\s|$)",
            "Jalan",
            teks,
            flags=re.IGNORECASE
        )

        # Normalisasi singkatan gang
        teks = re.sub(
            r"\bGG\.?(?=\s|$)",
            "Gang",
            teks,
            flags=re.IGNORECASE
        )

        # Normalisasi nomor rumah
        teks = re.sub(
            r"\b(?:NO|NOMOR)\.?(?=\s|\d|$)",
            "No.",
            teks,
            flags=re.IGNORECASE
        )

        # Rapikan spasi setelah No.
        teks = re.sub(r"\bNo\.\s*(?=\d)", "No. ", teks)

        return teks


    def transformKoordinat(self, lat: float, lng: float):
        """
        Transformasi koordinat WGS84 (Lat, Lng) ke meter lokal (x_meter, y_meter)
        menggunakan proyeksi Equirectangular lokal berpusat di KCU Pos Malang.
        """
        lat_rad = math.radians(lat)
        lng_rad = math.radians(lng)
        origin_lat_rad = math.radians(self.origin_lat)
        origin_lng_rad = math.radians(self.origin_lon)

        x_meter = self.earth_radius * (lng_rad - origin_lng_rad) * math.cos(origin_lat_rad)
        y_meter = self.earth_radius * (lat_rad - origin_lat_rad)

        return round(x_meter, 2), round(y_meter, 2)

    
    def geocode(self, alamat: str):
        """
        Geocoding menggunakan Google Maps API.
        Tidak menggunakan koordinat simulasi.
        """
        alamat_bersih = self.bersihkanAlamat(alamat)

        def gagal(pesan):
            return {
                "alamat_bersih": alamat_bersih,
                "latitude": None,
                "longitude": None,
                "x_meter": None,
                "y_meter": None,
                "status": "FAILED",
                "error": pesan
            }

        if not alamat_bersih:
            return gagal("Alamat kosong")

        if not self.api_key:
            return gagal("Google Maps API Key belum tersedia")

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"

            response = requests.get(
                url,
                params={
                    "address": f"{alamat_bersih}, Kota Malang, Jawa Timur, Indonesia",
                    "components": "country:ID",
                    "key": self.api_key
                },
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                return gagal(
                    f"Google Maps: {data.get('status', 'UNKNOWN_ERROR')}"
                )

            hasil = data["results"][0]

            # Pastikan hasil berada dalam wilayah administratif Kota Malang
            komponen = hasil.get("address_components", [])

            kota_valid = any(
                "administrative_area_level_2" in item.get("types", [])
                and item.get("long_name", "").strip().casefold()
                    in ("kota malang", "malang city")
                for item in komponen
            )

            if not kota_valid:
                return gagal("Hasil geocoding berada di luar Kota Malang")

            lokasi = hasil["geometry"]["location"]
            lat = float(lokasi["lat"])
            lng = float(lokasi["lng"])

            x_m, y_m = self.transformKoordinat(lat, lng)

            return {
                "alamat_bersih": alamat_bersih,
                "latitude": lat,
                "longitude": lng,
                "x_meter": x_m,
                "y_meter": y_m,
                "status": "SUCCESS"
            }

        except requests.RequestException as e:
            return gagal(f"Gagal menghubungi Google Maps: {e}")

        except (KeyError, TypeError, ValueError) as e:
            return gagal(f"Respons geocoding tidak valid: {e}")
