
import re
import unicodedata
import pandas as pd


# =====================================================
# 1. REFERENSI WILAYAH KOTA MALANG
# =====================================================

WILAYAH = {
    "BLIMBING": [
        "Balearjosari", "Arjosari", "Polowijen",
        "Purwodadi", "Pandanwangi", "Blimbing",
        "Purwantoro", "Bunulrejo", "Kesatrian",
        "Polehan", "Jodipan"
    ],
    "KLOJEN": [
        "Klojen", "Samaan", "Rampal Celaket",
        "Kiduldalem", "Sukoharjo", "Kasin",
        "Kauman", "Oro-oro Dowo", "Bareng",
        "Gading Kasri", "Penanggungan"
    ],
    "KEDUNGKANDANG": [
        "Kotalama", "Mergosono", "Bumiayu",
        "Wonokoyo", "Buring", "Kedungkandang",
        "Lesanpuro", "Sawojajar", "Madyopuro",
        "Cemorokandang", "Arjowinangun",
        "Tlogowaru"
    ],
    "SUKUN": [
        "Ciptomulyo", "Gadang", "Kebonsari",
        "Bandungrejosari", "Sukun",
        "Tanjungrejo", "Pisangcandi",
        "Bandulan", "Karangbesuki",
        "Mulyorejo", "Bakalan Krajan"
    ],
    "LOWOKWARU": [
        "Tunggulwulung", "Merjosari", "Tlogomas",
        "Dinoyo", "Sumbersari", "Ketawanggede",
        "Jatimulyo", "Tunjungsekar",
        "Mojolangu", "Tulusrejo", "Lowokwaru",
        "Tasikmadu"
    ]
}

assert len(WILAYAH) == 5
assert sum(len(v) for v in WILAYAH.values()) == 57


# =====================================================
# 2. NORMALISASI TEKS
# =====================================================

def norm(text):
    if text is None or pd.isna(text):
        return ""

    text = unicodedata.normalize(
        "NFKC", str(text)
    ).casefold()

    text = re.sub(r"[^a-z0-9]+", " ", text)

    return re.sub(r"\s+", " ", text).strip()


# =====================================================
# 3. PEMETAAN KELURAHAN DAN KECAMATAN
# =====================================================

KEL_TO_KEC = {
    norm(kel): kec.title()
    for kec, daftar in WILAYAH.items()
    for kel in daftar
}

KEL_DISPLAY = {
    norm(kel): kel
    for daftar in WILAYAH.values()
    for kel in daftar
}

KECAMATAN = {
    norm(kec): kec.title()
    for kec in WILAYAH
}


# =====================================================
# 4. ALIAS NAMA WILAYAH
# =====================================================

# Variasi penulisan wilayah yang diketahui.
# Tidak menggunakan fuzzy matching otomatis.

ALIAS_WILAYAH = {
    "pisang candi": "pisangcandi",
    "rampalcelaket": "rampal celaket",
    "kidul dalam": "kiduldalem",
    "oroorodowo": "oro oro dowo",
    "gadingkasri": "gading kasri",
    "karang besuki": "karangbesuki",
    "bakalan krajan": "bakalan krajan",
    "bandung rejosari": "bandungrejosari",
    "kota lama": "kotalama"
}


# =====================================================
# 5. PENCOCOKAN NAMA WILAYAH
# =====================================================

def cocok_nama(teks, daftar_nama):
    """
    Mencari nama wilayah dengan ketentuan:
    - Tidak sensitif huruf kapital.
    - Mendukung spasi berulang.
    - Mendukung alias wilayah.
    - Tidak mencocokkan substring di dalam kata.
    """

    teks_normal = norm(teks)
    token = teks_normal.split()
    ditemukan = set()

    for nama in daftar_nama:
        bentuk = {norm(nama)}

        for alias, standar in ALIAS_WILAYAH.items():
            if norm(standar) == norm(nama):
                bentuk.add(norm(alias))

        for variasi in bentuk:
            bagian = variasi.split()

            pola = r"\b" + r"\s+".join(
                re.escape(x) for x in bagian
            ) + r"\b"

            if re.search(pola, teks_normal):
                ditemukan.add(nama)
                break

            # Mendukung nama wilayah yang terpisah
            # spasi, seperti LOWOK WARU dan DINO YO.
            target = "".join(bagian)

            for i in range(len(token)):
                for j in range(
                    i + 1,
                    min(i + 4, len(token)) + 1
                ):
                    kandidat = "".join(token[i:j])

                    if kandidat == target:
                        ditemukan.add(nama)
                        break

                if nama in ditemukan:
                    break

    return ditemukan


# =====================================================
# 6. PEMISAHAN BAGIAN NAMA JALAN
# =====================================================

def pisahkan_bagian_jalan(alamat):
    """
    Melindungi bagian nama jalan sebelum
    mendeteksi kelurahan dan kecamatan.

    Jika batas nama jalan tidak dapat
    dipastikan, gunakan pendekatan konservatif.
    """

    teks = norm(alamat)

    pola = (
        r"\b(?:jl|jalan|gg|gang)\b"
        r".*?(?="
        r"\b(?:no|nomor|rt|rw|blok|"
        r"kel|kelurahan|kec|kecamatan)\b"
        r"|\b\d+[a-z]?\b"
        r"|$)"
    )

    bagian_jalan = re.findall(pola, teks)

    sisa = re.sub(pola, " ", teks)
    sisa = re.sub(r"\s+", " ", sisa).strip()

    return bagian_jalan, sisa


# =====================================================
# 7. PEMERIKSAAN LABEL KELURAHAN / KECAMATAN
# =====================================================

def ada_label(teks, jenis, nama):
    teks = norm(teks)
    nama = norm(nama)

    if jenis == "kel":
        label = r"(?:kel|kelurahan)"
    else:
        label = r"(?:kec|kecamatan)"

    pola = rf"\b{label}\s+{re.escape(nama)}\b"

    return bool(re.search(pola, teks))


# =====================================================
# 8. DETEKSI WILAYAH DARI ALAMAT
# =====================================================

def deteksi_wilayah_alamat(alamat):
    """
    Mendeteksi kelurahan dan kecamatan
    berdasarkan informasi dalam alamat.

    Menghasilkan:
    - Kelurahan terdeteksi.
    - Kecamatan terdeteksi.
    - Daftar kandidat wilayah.
    - Catatan ambiguitas.
    """

    _, sisa = pisahkan_bagian_jalan(alamat)

    kel_candidates = cocok_nama(
        sisa,
        KEL_TO_KEC.keys()
    )

    kec_candidates = cocok_nama(
        sisa,
        KECAMATAN.keys()
    )

    catatan = []

    # Nama wilayah yang sekaligus merupakan
    # kelurahan dan kecamatan.
    nama_ganda = kel_candidates & kec_candidates

    for nama in nama_ganda:
        eksplisit_kel = ada_label(
            sisa, "kel", nama
        )

        eksplisit_kec = ada_label(
            sisa, "kec", nama
        )

        if eksplisit_kel and not eksplisit_kec:
            kec_candidates.discard(nama)

        elif eksplisit_kec and not eksplisit_kel:
            kel_candidates.discard(nama)

        elif not eksplisit_kel and not eksplisit_kec:
            kel_candidates.discard(nama)

            catatan.append(
                f"Nama wilayah ganda: {nama}"
            )

    kel = None
    kec = None

    if len(kel_candidates) == 1:
        kel = next(iter(kel_candidates))

    elif len(kel_candidates) > 1:
        catatan.append(
            "Beberapa kelurahan terdeteksi di alamat"
        )

    if len(kec_candidates) == 1:
        kec = next(iter(kec_candidates))

    elif len(kec_candidates) > 1:
        catatan.append(
            "Beberapa kecamatan terdeteksi di alamat"
        )

    # Menentukan kecamatan induk dari kelurahan.
    if kel:
        kec_induk = norm(KEL_TO_KEC[kel])

        if kec and kec != kec_induk:
            catatan.append(
                "Konflik kelurahan dan kecamatan di alamat"
            )

        elif not kec:
            kec = kec_induk

    return {
        "kel": kel,
        "kec": kec,
        "kel_ditemukan": kel_candidates,
        "kec_ditemukan": kec_candidates,
        "catatan": catatan
    }


# =====================================================
# 9. DETEKSI WILAYAH DARI KOLOM KOTA
# =====================================================

def deteksi_wilayah_kota(kota):
    """
    Format yang diharapkan:
    KOTA MALANG, KECAMATAN, KELURAHAN

    Kolom Kota digunakan sebagai informasi
    pelengkap, bukan sebagai bukti lokasi.
    """

    bagian = [
        norm(x)
        for x in re.split(r"[,;]", str(kota or ""))
        if norm(x)
    ]

    if not bagian:
        return None, None, False

    valid_city = bagian[0] in {
        "kota malang",
        "malang",
        "kota mlg",
        "mlg"
    }

    if not valid_city:
        return None, None, False


    kec = bagian[1] if len(bagian) > 1 else None
    kel = bagian[2] if len(bagian) > 2 else None

    # Normalisasi alias wilayah dari kolom Kota.
    if kec:
        kec = norm(ALIAS_WILAYAH.get(kec, kec))

    if kel:
        kel = norm(ALIAS_WILAYAH.get(kel, kel))

    if kec not in KECAMATAN:
        kec = None

    if kel not in KEL_TO_KEC:
        kel = None


    # Pastikan kelurahan dan kecamatan cocok.
    if kel and kec:
        if norm(KEL_TO_KEC[kel]) != kec:
            return None, None, True

    if kel and not kec:
        kec = norm(KEL_TO_KEC[kel])

    return kel, kec, True


# =====================================================
# 10. PEMBERSIHAN AKHIRAN ALAMAT
# =====================================================

def bersihkan_akhiran_alamat(alamat):
    """
    Membersihkan konteks administratif berulang.

    Ketentuan:
    - Kata MALANG berdiri sendiri dipertahankan.
    - KOTA MALANG dihapus karena ditambahkan
      kembali pada akhir query.
    - JAWA TIMUR dihapus jika mengikuti
      konteks administratif KOTA MALANG.
    - Nama jalan, institusi, dan kode pos
      dipertahankan.
    """

    teks = str(alamat).strip()

    if not teks:
        return ""

    teks = re.sub(
        r"\bkota\s+malang"
        r"(?:[\s,;\-]+jawa\s+timur)?\b",
        " ",
        teks,
        flags=re.IGNORECASE
    )

    teks = re.sub(r"\s+", " ", teks)
    teks = re.sub(r"\s+([,;])", r"\1", teks)
    teks = re.sub(r"[,;]\s*[,;]+", ", ", teks)

    return teks.strip(" ,;-")


# =====================================================
# 11. ADAPTIVE SINGLE QUERY
# =====================================================

def buat_satu_query(alamat, kota=""):
    """
    Menyusun satu query untuk Google Maps
    Geocoding API.

    Prioritas:
    1. Informasi wilayah dari alamat.
    2. Kolom Kota sebagai pelengkap.
    3. Konteks Kota Malang, Jawa Timur,
       Indonesia.

    Tidak melakukan permintaan API.
    Tidak mengubah alamat asli.
    """

    alamat_asli = (
        "" if pd.isna(alamat)
        else str(alamat).strip()
    )

    kota_asli = (
        "" if pd.isna(kota)
        else str(kota).strip()
    )

    def hasil(kel, kec, sumber, status, catatan, query):
        return {
            "Kelurahan Deteksi": (
                KEL_DISPLAY[kel] if kel else ""
            ),
            "Kecamatan Deteksi": (
                KECAMATAN[kec] if kec else ""
            ),
            "Sumber Wilayah": sumber,
            "Status Deteksi": status,
            "Catatan": catatan,
            "Query Akhir": query
        }

    if not alamat_asli:
        return hasil(
            None,
            None,
            "",
            "ALAMAT KOSONG",
            "Alamat tidak tersedia",
            ""
        )

    # Deteksi wilayah dari alamat.
    det_alamat = deteksi_wilayah_alamat(
        alamat_asli
    )

    kel = det_alamat["kel"]
    kec = det_alamat["kec"]

    # Deteksi wilayah dari kolom Kota.
    kel_kota, kec_kota, valid_city = (
        deteksi_wilayah_kota(kota_asli)
    )

    catatan = det_alamat["catatan"].copy()
    sumber = []

    if kel or kec:
        sumber.append("Alamat")

    konflik_alamat = any(
        "Konflik kelurahan dan kecamatan" in x
        for x in catatan
    )

    # Kolom Kota tidak digunakan apabila
    # informasi wilayah dalam alamat bertentangan.
    if valid_city and not konflik_alamat:

        if kel:
            # Prioritaskan kelurahan dari alamat.
            if kel_kota and kel_kota != kel:
                catatan.append(
                    "Kelurahan kolom Kota berbeda"
                )

            if kec_kota and kec_kota != kec:
                catatan.append(
                    "Kecamatan kolom Kota berbeda"
                )

        elif kec:
            # Alamat hanya memiliki kecamatan.
            # Lengkapi kelurahan jika sesuai.
            if kel_kota:
                kec_induk = norm(
                    KEL_TO_KEC[kel_kota]
                )

                if kec_induk == kec:
                    kel = kel_kota
                    sumber.append("Kolom Kota")
                else:
                    catatan.append(
                        "Kelurahan kolom Kota tidak cocok"
                    )

            if kec_kota and kec_kota != kec:
                catatan.append(
                    "Kecamatan kolom Kota berbeda"
                )

        else:
            # Tidak ada wilayah dalam alamat.
            # Gunakan kolom Kota yang valid.
            if kel_kota:
                kel = kel_kota
                kec = norm(KEL_TO_KEC[kel])
                sumber.append("Kolom Kota")

            elif kec_kota:
                kec = kec_kota
                sumber.append("Kolom Kota")

    # Bersihkan konteks administratif berulang.
    query_alamat = bersihkan_akhiran_alamat(
        alamat_asli
    )

    tambahan = []

    # Tambahkan kelurahan jika belum ada
    # pada bagian alamat.
    if kel and kel not in det_alamat["kel_ditemukan"]:
        tambahan.append(
            f"Kelurahan {KEL_DISPLAY[kel]}"
        )

    # Tambahkan kecamatan jika belum ada
    # pada bagian alamat.
    if kec and kec not in det_alamat["kec_ditemukan"]:
        tambahan.append(
            f"Kecamatan {KECAMATAN[kec]}"
        )

    bagian_query = [
        query_alamat,
        *tambahan,
        "Kota Malang",
        "Jawa Timur",
        "Indonesia"
    ]

    query = ", ".join(
        x for x in bagian_query if x
    )

    if catatan:
        status = "PERLU CEK"

    elif kel or kec:
        status = "TERDETEKSI"

    else:
        status = "WILAYAH RINCI TIDAK TERDETEKSI"

    return hasil(
        kel,
        kec,
        " + ".join(dict.fromkeys(sumber)),
        status,
        "; ".join(dict.fromkeys(catatan)),
        query
    )
