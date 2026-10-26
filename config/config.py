import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "geokurir-malang-super-secret-key-2026")
    
    # Google Maps Platform Configuration (Geocoding & Map Rendering)
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Batas Jumlah Data Geocoding & Modeling
    # None = memproses seluruh data; angka (misal 22, 50, 100) = membatasi N data
    _raw_limit = os.getenv("GEOCODING_LIMIT", "None")
    GEOCODING_LIMIT = int(_raw_limit) if (_raw_limit and str(_raw_limit).strip().lower() not in ("", "none", "null", "all", "semua") and _raw_limit.strip().isdigit()) else None

    # PostgreSQL Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_USER = os.getenv("DB_USER", "geokurir")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "geokurir_secret")
    DB_NAME = os.getenv("DB_NAME", "geokurir_db")

    # KCU Pos Malang Origin Coordinates
    KCU_ORIGIN_LAT = -7.9835954
    KCU_ORIGIN_LON = 112.6303597
    KCU_NAME = "PT Pos Indonesia KCU Malang"

    # Server Configuration
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "t")

    @classmethod
    def get_db_connection_params(cls):
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "dbname": cls.DB_NAME,
        }
