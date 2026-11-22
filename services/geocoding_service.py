import math
import json
import requests
import time

from pathlib import Path
from shapely.geometry import Point, shape
from config import Config
from .query import buat_satu_query


class GeocodingService:
    """
    Layanan geocoding GeoKurir Malang.

    Menerima alamat_bersih hasil preprocessing,
    mengambil koordinat melalui Google Maps Geocoding API,
    memvalidasi hasil dalam wilayah Kota Malang,
    dan mentransformasikan koordinat menjadi meter lokal
    relatif terhadap KCU Pos Malang.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self.origin_lat = Config.KCU_ORIGIN_LAT
        self.origin_lon = Config.KCU_ORIGIN_LON
        self.earth_radius = 6371000.0
        # Memuat poligon administratif Kota Malang
        base_dir = Path(__file__).resolve().parent.parent

        geojson_path = (
            base_dir / "data" / "batas_kota_malang.geojson"
        )

        with open(geojson_path, "r", encoding="utf-8") as file:
            geojson = json.load(file)

        features = geojson.get("features", [])

        if len(features) != 1:
            raise ValueError(
                "GeoJSON Kota Malang harus memiliki tepat 1 fitur"
            )

        self.poligon_kota = shape(
            features[0]["geometry"]
        )

        if (
            not self.poligon_kota.is_valid
            or self.poligon_kota.is_empty
        ):
            raise ValueError(
                "Geometri poligon Kota Malang tidak valid"
            )
        
        min_lng, min_lat, max_lng, max_lat = self.poligon_kota.bounds

        self.geocode_bounds = (
            f"{min_lat},{min_lng}|{max_lat},{max_lng}"
        )

    def transformKoordinat(self, lat: float, lng: float):
        """
        Transformasi koordinat WGS84 (Lat, Lng)
        ke meter lokal (x_meter, y_meter)
        menggunakan proyeksi Equirectangular lokal
        berpusat di KCU Pos Malang.
        """
        lat_rad = math.radians(lat)
        lng_rad = math.radians(lng)
        origin_lat_rad = math.radians(self.origin_lat)
        origin_lng_rad = math.radians(self.origin_lon)

        x_meter = (
            self.earth_radius
            * (lng_rad - origin_lng_rad)
            * math.cos(origin_lat_rad)
        )

        y_meter = (
            self.earth_radius
            * (lat_rad - origin_lat_rad)
        )

        return round(x_meter, 2), round(y_meter, 2)

    def cek_wilayah(self, lat: float, lng: float):
        """
        Memeriksa apakah koordinat berada di dalam
        atau tepat pada batas administratif Kota Malang.
        """
        titik = Point(lng, lat)

        return self.poligon_kota.covers(titik)



    def geocode(self, alamat: str, kota: str = ""):
        """
        Geocoding menggunakan 1 query Google Maps API.

        Alur:
        1. Geocoding alamat_bersih.
        2. Periksa kandidat koordinat.
        3. Validasi Point-in-Polygon Kota Malang.
        4. Transformasi koordinat menjadi meter lokal.

        """

        alamat_bersih = (
            str(alamat).strip()
            if alamat is not None
            else ""
        )

        kota_asli = str(kota).strip() if kota is not None else ""

        # Susun satu query menggunakan Adaptive Single Query
        hasil_query = buat_satu_query(
            alamat_bersih,
            kota_asli
        )

        query_alamat = hasil_query["Query Akhir"]
        print(
            f"[DEBUG QUERY] query={query_alamat!r}",
            flush=True
        )

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

        print(
            f"[DEBUG GEOCODING] "
            f"alamat={alamat!r} | kota={kota!r}",
            flush=True
        )

        if not alamat_bersih:
            return gagal("Alamat kosong")

        if not self.api_key:
            return gagal("Google Maps API Key belum tersedia")

        url = "https://maps.googleapis.com/maps/api/geocode/json"

        try:
            # Retry otomatis maksimal 3 kali jika koneksi gagal
            for percobaan in range(1, 4):
                try:
                    response = requests.get(
                        url,
                        params={
                            "address": query_alamat,
                            "bounds": self.geocode_bounds,
                            "components": "country:ID",
                            "region": "id",
                            "key": self.api_key
                        },
                        timeout=(5, 30)
                    )

                    break

                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError
                ) as e:

                    print(
                        f"[GEOCODING RETRY] "
                        f"Percobaan {percobaan}/3 gagal: {e}",
                        flush=True
                    )

                    if percobaan == 3:
                        return gagal(
                            "Gagal menghubungi Google Maps "
                            f"setelah 3 percobaan: {e}"
                        )

                    time.sleep(2 * percobaan)

            response.raise_for_status()
            data = response.json()

            api_status = data.get(
                "status",
                "UNKNOWN_ERROR"
            )

            if api_status == "ZERO_RESULTS":
                return gagal(
                    "Alamat tidak ditemukan oleh Google Maps"
                )

            if api_status != "OK":
                pesan_error = {
                    "OVER_QUERY_LIMIT":
                        "Batas permintaan Google Maps API terlampaui",
                    "OVER_DAILY_LIMIT":
                        "Batas penggunaan Google Maps API bermasalah",
                    "REQUEST_DENIED":
                        "Permintaan ditolak oleh Google Maps API",
                    "INVALID_REQUEST":
                        "Parameter geocoding tidak valid",
                    "UNKNOWN_ERROR":
                        "Terjadi gangguan sementara pada Google Maps API"
                }

                return gagal(
                    pesan_error.get(
                        api_status,
                        f"Google Maps API: {api_status}"
                    )
                )

            if not data.get("results"):
                return gagal(
                    "Tidak ada kandidat koordinat dari Google Maps"
                )

            alasan_penolakan = []
            ada_koordinat_valid = False
            ada_lokasi_spesifik = False

            for hasil in data["results"]:
                try:
                    lokasi = hasil["geometry"]["location"]

                    lat = float(lokasi["lat"])
                    lng = float(lokasi["lng"])
                    ada_koordinat_valid = True

                except (KeyError, TypeError, ValueError):
                    alasan_penolakan.append(
                        "Kandidat tidak memiliki koordinat valid"
                    )
                    continue

                # Tolak hasil yang hanya menunjukkan negara
                tipe_lokasi = hasil.get("types", [])

                if "country" in tipe_lokasi:
                    alasan_penolakan.append(
                        "Hasil geocoding hanya menunjukkan negara"
                    )
                    continue

                ada_lokasi_spesifik = True

                alamat_google = hasil.get(
                    "formatted_address", "-"
                )

                # Validasi PIP Kota Malang
                if not self.cek_wilayah(lat, lng):
                    alasan_penolakan.append(
                        f"Di luar poligon Kota Malang: {alamat_google}"
                    )
                    continue

                # Koordinat lolos PIP
                x_m, y_m = self.transformKoordinat(
                    lat, lng
                )

                return {
                    "alamat_bersih": alamat_bersih,
                    "latitude": lat,
                    "longitude": lng,
                    "x_meter": x_m,
                    "y_meter": y_m,
                    "status": "SUCCESS"
                }

            if not ada_koordinat_valid or not ada_lokasi_spesifik:
                return gagal(
                    "Alamat tidak ditemukan oleh Google Maps"
                )

            return gagal(
                "Di luar poligon Kota Malang: "
                + " | ".join(alasan_penolakan[:3])
            )

        except requests.RequestException as e:
            return gagal(
                f"Gagal menghubungi Google Maps: {e}"
            )

        except (KeyError, TypeError, ValueError) as e:
            return gagal(
                f"Respons geocoding tidak valid: {e}"
            )
