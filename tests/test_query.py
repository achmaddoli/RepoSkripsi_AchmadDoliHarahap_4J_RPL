
from services.query import buat_satu_query

data_uji = [
    (
        "JL IKAN KAKAP NO 20 TUNJUNGSEKAR",
        "KOTA MALANG, LOWOKWARU, TUNJUNGSEKAR"
    ),
    (
        "JL SOEKARNO HATTA NO 10",
        "KOTA MALANG, LOWOKWARU, MOJOLANGU"
    ),
    (
        "JL GAJAYANA NO 5 SUMBERSARI",
        "KOTA MALANG, LOWOKWARU, SUMBERSARI"
    ),
    (
        "JL MERDEKA NO 3 KLOJEN",
        "KOTA MALANG, KLOJEN, KLOJEN"
    ),
    (
        "JL CONTOH NO 15 PISANG CANDI",
        "KOTA MALANG, SUKUN, PISANG CANDI"
    ),
    (
        "JL CONTOH NO 12 KIDUL DALAM",
        "KOTA MALANG, KLOJEN, KIDULDALEM"
    ),
    (
        "JL CONTOH NO 7 ORO-ORO DOWO",
        "KOTA MALANG, KLOJEN, ORO-ORO DOWO"
    ),
    (
        "JL CONTOH NO 8 TUNJUNGSEKAR",
        "KOTA MALANG, SUKUN, PISANGCANDI"
    ),
    (
        "JL SOEKARNO HATTA MOJOLANGU",
        "KOTA MALANG, LOWOKWARU, MOJOLANGU"
    ),
    (
        "JL RAYA KARANGPLOSO NO 10",
        "KAB MALANG, KARANGPLOSO"
    )
]

for nomor, (alamat, kota) in enumerate(data_uji, start=1):
    hasil = buat_satu_query(alamat, kota)

    print(f"\n{'=' * 70}")
    print(f"DATA {nomor}")
    print(f"{'=' * 70}")
    print(f"Alamat          : {alamat}")
    print(f"Kota            : {kota}")
    print(f"Kelurahan       : {hasil['Kelurahan Deteksi']}")
    print(f"Kecamatan       : {hasil['Kecamatan Deteksi']}")
    print(f"Sumber Wilayah  : {hasil['Sumber Wilayah']}")
    print(f"Status          : {hasil['Status Deteksi']}")
    print(f"Catatan         : {hasil['Catatan']}")
    print(f"QUERY AKHIR     : {hasil['Query Akhir']}")

print("\nTESTING SELESAI")
