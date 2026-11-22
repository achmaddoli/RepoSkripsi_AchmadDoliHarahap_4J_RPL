import os
import requests

from config import Config
from services.geocoding_service import GeocodingService
from shapely.geometry import Point

ALAMAT = "Perum cityside residence, Blk. R Jl. Lowokdoro No.1, Kebonsari, Kec. Sukun, Kota Malang, Jawa Timur 65162"

service = GeocodingService()

min_lng, min_lat, max_lng, max_lat = service.poligon_kota.bounds
bounds = f"{min_lat},{min_lng}|{max_lat},{max_lng}"

response = requests.get(
    "https://maps.googleapis.com/maps/api/geocode/json",
    params={
        "address": ALAMAT,
        "bounds": bounds,
        "components": "country:ID",
        "region": "id",
        "key": os.getenv("GOOGLE_MAPS_API_KEY")
    },
    timeout=10
)

response.raise_for_status()
data = response.json()

print("Status API:", data.get("status"))
print("Pesan error:", data.get("error_message", "-"))

for hasil in data.get("results", []):
    lokasi = hasil["geometry"]["location"]
    lat = lokasi["lat"]
    lng = lokasi["lng"]

    wilayah = [
        item["long_name"]
        for item in hasil.get("address_components", [])
        if "administrative_area_level_2" in item.get("types", [])
    ]

    administratif_valid = any(
        nama.strip().casefold() in ("kota malang", "malang city")
        for nama in wilayah
    )

    pip_valid = service.poligon_kota.covers(Point(lng, lat))

    print("\nAlamat Google:", hasil.get("formatted_address"))
    print("Wilayah administratif:", wilayah)
    print("Tipe hasil:", hasil.get("types"))
    print("Akurasi:", hasil["geometry"].get("location_type"))
    print("Koordinat:", lat, lng)
    print("Administratif Kota Malang:", administratif_valid)
    print("PIP Kota Malang:", pip_valid)
    print(
        "Kesimpulan:",
        "SESUAI" if administratif_valid == pip_valid else "BERBEDA"
    )
