# GeoKurir audit: menjalankan fungsi geocode asli website 1x per alamat.
# Pemakaian: Get-Content -Raw -Encoding UTF8 .\audit_49_geokurir.py | docker compose exec -T web python - | Set-Content -Encoding UTF8 .\hasil_audit_49_gmaps.csv
import csv
import io
import json
import sys
from contextlib import redirect_stdout
from unittest.mock import patch
import requests

from config import Config
from services.geocoding_service import GeocodingService
from services.query import buat_satu_query, norm, KEL_TO_KEC, KEL_DISPLAY, KECAMATAN

RECORDS = [
  {
    "No": 1,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2507300186477",
    "Alamat Asli": "Jl Raya Langsep No62, Pisang Candi, Kec Sukun, Kota Malang, Jawa Timur",
    "Kota Asli": "KOTA MALANG, KLOJEN, BARENG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 2,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310078761",
    "Alamat Asli": "ASRAMA DEDIKJUR RINDEM V BRAWIJAYA JL MEYKA M WIYANA NO 1 POLEHAN BLIMBING MALANG",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, KETAWANGGEDE",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 3,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310109875",
    "Alamat Asli": "JL VETERAN NO 9 SUMBERSARI ,LOWOKWARU ,MALANG",
    "Kota Asli": "KOTA MALANG, KLOJEN, PENANGGUNGAN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 4,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310121426",
    "Alamat Asli": "JL. SIMPANG BOROBUDUR UTARA 1 BOJOLANGO PASAR BLIMBING DEKATH SDN BLIMBING 5 RT 5 RW 15",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, MOJOLANGU",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 5,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310132824",
    "Alamat Asli": "JL. INDRAGIRI KAVLING GG I A PURWANTORO KEC BLIMBING KOTA MALANG 65122",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, TULUSREJO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 6,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310176095",
    "Alamat Asli": "Bank Sinarmas Syariah  Jalan Letjen Sutoyo No  88  Bunulrejo  Blimbing  Bank nano syariah",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, LOWOKWARU",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 7,
    "Dataset": "01 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "SHPE250731DCC5A08970",
    "Alamat Asli": "Jalan Muharto No 02  RT 01 RW 04   warung pojok SURADI CUKAM  Kelurahan Kotalama  Kedungkandang",
    "Kota Asli": "KOTA MALANG, BLIMBING, JODIPAN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 8,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2507310116444",
    "Alamat Asli": "JL POLONIA BM 13 RT 05 RW 09 CEMOROKANDANG KEC KEDUNG KANDANG",
    "Kota Asli": "KOTA MALANG, BLIMBING, PANDANWANGI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 9,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310055764",
    "Alamat Asli": "JL KOL SUGIONO 5D 35/49 RT 14 RW 03 KEL MERGOSONO KEC KEDUNGKANDANG MALANG JAWA TIMUR",
    "Kota Asli": "KOTA MALANG, SUKUN, GADANG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 10,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310089789",
    "Alamat Asli": "jl muharto gg permadi rt 02 rw 08 kelurahan jodipan kecamatan blimbing depan gg 5 muharto  samping tahwa",
    "Kota Asli": "KOTA MALANG, KEDUNGKANDANG, KOTALAMA",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 11,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310106221",
    "Alamat Asli": "Jalan Kol Sugiono 3B No 59  RT 11 RW 5  Mergosono  Kedungkandang  Ibu jaenab agus",
    "Kota Asli": "KOTA MALANG, SUKUN, GADANG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 12,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310181271",
    "Alamat Asli": "JALAN KOL SUGIONO VII/30 RT 009/002 KEL. MERGOSONO KEC. KEDUNGKANDANG",
    "Kota Asli": "KOTA MALANG, SUKUN, GADANG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 13,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010005060",
    "Alamat Asli": "JL KAVALERI IVAR NO H64 RT01 RW06 KESATRIAN BLIMBING MALANG",
    "Kota Asli": "KOTA MALANG, KLOJEN, ORO-ORO DOWO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 14,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010036170",
    "Alamat Asli": "PERUM PURI KARTIKA ASRI  BLOK  X-6 RT/RW 005/009  KEL ARJOWINANGUN KEC KEDUNG KANDANG  KOTA MALANG",
    "Kota Asli": "KOTA MALANG, BLIMBING, PURWODADI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 15,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010120753",
    "Alamat Asli": "JL RAYA CANDI VI NANTI 4 RT 2 RW 7 KEL.DINOYO KEC.LOWOKWARU MALANG JAWA TIMUR 65144",
    "Kota Asli": "KOTA MALANG, SUKUN, KARANGBESUKI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 16,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010151516",
    "Alamat Asli": "Jalan Kaliurang No 59  Rampal Celaket  Klojen  RT  001   RW  006",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, LOWOKWARU",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 17,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "SHPE25073151AFB24666",
    "Alamat Asli": "Gg  V  No 385a  Sumbersari  Lowokwaru  Depan sdn sumbersari",
    "Kota Asli": "KOTA MALANG, KEDUNGKANDANG, KOTALAMA",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 18,
    "Dataset": "02 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2507310043466",
    "Alamat Asli": "Jl. Borobudur No.33, Kel. Kauman, Kec. Klojen Kota Malang 65142",
    "Kota Asli": "KOTA MALANG, BLIMBING, BLIMBING",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 19,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508010066556",
    "Alamat Asli": "JL. KOLIBRI NO. 31 KASIN KLOJEN MALANG, 65117,JAWA TIMUR",
    "Kota Asli": "KOTA MALANG, SUKUN, SUKUN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 20,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508010067187",
    "Alamat Asli": "Denpom V 3 Brawijaya  Jalan Kesatrian No  1  Kesatrian  Blimbing",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, KETAWANGGEDE",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 21,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508010067936",
    "Alamat Asli": "JL. KOLIBRI NO. 31 KASIN KLOJEN MALANG 65117 JATIM",
    "Kota Asli": "KOTA MALANG, SUKUN, SUKUN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 22,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508010158817",
    "Alamat Asli": "JL. I.R. RAIS IX / 298 RT 008 RW 004 KEL. TANJUNGREJO, KEC. SUKUN, KOT",
    "Kota Asli": "KOTA MALANG, KLOJEN, BARENG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 23,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508010158909",
    "Alamat Asli": "JL.IR. RAIS IX / 298 RT 008 RW004 KEL TANJUNGREJO KEC SUKUN KOTA MALANG",
    "Kota Asli": "KOTA MALANG, KLOJEN, BARENG",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 24,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508020011769",
    "Alamat Asli": "JL JOYO TAMANSARI NO 33 KEL TANJUNGREJO KEC SUKUN KOTA MALANG",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, MERJOSARI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 25,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010017114",
    "Alamat Asli": "JL. KAWI 23 RT003/002 BARENG, KLOJEN MALANG 65116 JAWA TIMUR",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, JATIMULYO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 26,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010159062",
    "Alamat Asli": "JL KOL SUGIONO GANG 21C RT 06 RW 04 KEL. GADANG KEC. SUKUN KOTA MALANG",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 27,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "SHPE2508012DE3A20633",
    "Alamat Asli": "Jl  Veteran No 2  Penanggungan  Kec  Klojen  Kota Malang  Jawa Timur OSAKA DESU   Food court lantai UG",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, JATIMULYO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 28,
    "Dataset": "03 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508010095432",
    "Alamat Asli": "Jln kelapa sawit gang10 no 01 RT 03 RW 03, pisang candi, kec. sukun, kota Malang, jatim (TUGINGO HERBAL)",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 29,
    "Dataset": "04 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508020011880",
    "Alamat Asli": "Jl. Borobudur No.33, Kel. Kauman, Kec. Klojen Kota Malang 65142",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, TUNJUNGSEKAR",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 30,
    "Dataset": "04 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508020070367",
    "Alamat Asli": "Perum Taman Raden Intan Kav 546 RT 03 RW 04 Kelurahan Arjosari Kec Blimbing Kota Malang Jawa Timur (TUGINGO HERBAL)",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 31,
    "Dataset": "04 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508020059024",
    "Alamat Asli": "SUKUN BANDULAN JL ISTANA DIENG SELATAN I/28 RT001 RW007 JAWA MALANG",
    "Kota Asli": "KOTA MALANG, KLOJEN, GADING KASRI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 32,
    "Dataset": "04 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508020099887",
    "Alamat Asli": "MALANG CITY POINT JL DIENG NO 31 LT 1 PISANG CANDI SUKUN",
    "Kota Asli": "KOTA MALANG, KLOJEN, GADING KASRI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 33,
    "Dataset": "05 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040154122",
    "Alamat Asli": "Perumahan Bulan Terang Utama  Jalan Raya Ki Ageng Gribig Blok Uj 21 No  10  Madyopuro  Kedungkandang",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 34,
    "Dataset": "05 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040170980",
    "Alamat Asli": "JL POLOWIJEN II NO 316 ARJOSARI BLIMBING",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 35,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508040116376",
    "Alamat Asli": "(FLAT) JLN SULFAT AGUNG BOULEVARD NO 3 KOTA MALANG KEL PURWANTORO KEC BLIMBING KOTA MALANG RT/RW 2/1",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 36,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508040124738",
    "Alamat Asli": "Ksp citra abadi jln raya gadang 36, kec. sukun, kab. malang, jatim (TUGINGO HERBAL)",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 37,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508040131535",
    "Alamat Asli": "Jl. Ikan Gurami No.28, Tunjungsekar, Kec. Lowokwaru,Rt 03. Rw.06 Kota Malang, Jawa Timur 65142, Indonesia",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 38,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "SHPE2508042EEF005726",
    "Alamat Asli": "Jalan Ikan Hiu  RT 2 RW 5  Tunjung Sekar  Tunjungsekar  Lowokwaru  No 4",
    "Kota Asli": "KOTA MALANG, BLIMBING, KESATRIAN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 39,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040027121",
    "Alamat Asli": "Jl. Simpang Taman Agung No.23 GADINGKASRI, KLOJEN MALANG 65115 JAWA TIMUR",
    "Kota Asli": "KOTA MALANG, SUKUN, PISANG CANDI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 40,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040190615",
    "Alamat Asli": "JLN KYAI PARSEH JAYA RT 003 RW 016 KEL BUMIAYU KEC KEDUNGKANDANG KOTA",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 41,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040124109",
    "Alamat Asli": "Perum Bulan Terang Utama blok UJ 29/11 RT 006 RW 017, Kelurahan Madyopuro, Kec Kedungkandang, Kota Malang, Jawa Timur (HUBUNGI PEMBELI ISI SREVOT HERBAL)",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 42,
    "Dataset": "06 Agustus 2025",
    "Shift": "Shift Siang",
    "No Resi": "P2508040129342",
    "Alamat Asli": "Jln. Babatan GG.1/B.3 kelurahan Arjowinangun, Kec. Kedungkandang, Kota Malang, Jawa Timur",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 43,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050042222",
    "Alamat Asli": "JL PUNCAK MANDALA 44-B RT 07/10 PISANG CANDI SUKUN MALANG",
    "Kota Asli": "KOTA MALANG, BLIMBING, PURWODADI",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 44,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050067187",
    "Alamat Asli": "JL. SIMPANG DIRGANTARA IV A4/29 RT. 009 RW. 010, KEL. LESANPURO KEC. KEDUNG KANDANG  MALANG JATIM",
    "Kota Asli": "KOTA MALANG, BLIMBING, PURWANTORO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 45,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050100090",
    "Alamat Asli": "KUA KecSukun Jl Randu Jaya No2 Kel Bandungrejosari Kec Sukun Kota Malang",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 46,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050106647",
    "Alamat Asli": "MPT BUANA INDOMOBIL TRADA TEKNISI MOBIL JL LETJEND S PARMAN NO 63 PURWANTORO BLIMBING MALANG",
    "Kota Asli": "KOTA MALANG, LOWOKWARU, JATIMULYO",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 47,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050114213",
    "Alamat Asli": "Jl Puncak Trikora R2/06 Rt 008 Rw 007 Kel Karangbesuki Kec Sukun Malang",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 48,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050139722",
    "Alamat Asli": "Cluster arumba Indah Blok A no. 4, kel. tunggulwulung, kec. Lowokwaru, kota malang, jawatimur (TUGINGO HERBAL)",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  },
  {
    "No": 49,
    "Dataset": "07 Agustus 2025",
    "Shift": "Shift Pagi",
    "No Resi": "P2508050121968",
    "Alamat Asli": "Jln. Wonorejo No. 72P RT 003/RW 004, Kel. Arjowinangun, Kedungkandang, Kota Malang, Jawa Timur (Timur Masjid Miftahul Huda Masuk Gang Ke Utara",
    "Kota Asli": "KOTA MALANG, KLOJEN, KLOJEN",
    "Jenis Konflik": "KELURAHAN DAN KECAMATAN TIDAK SESUAI"
  }
]

service = GeocodingService(api_key=Config.GOOGLE_MAPS_API_KEY)
original_get = requests.get

FIELDS = [
    'No', 'Dataset', 'Shift', 'No Resi', 'Alamat Asli', 'Kota Asli',
    'Jenis Konflik', 'Query Akhir', 'Kelurahan Deteksi', 'Kecamatan Deteksi',
    'Catatan Query', 'Status Website', 'Error Website',
    'Status API', 'Alamat Google Maps', 'Latitude', 'Longitude',
    'Akurasi', 'Partial Match', 'PIP', 'Komponen Google Maps',
    'Kecamatan Google Kandidat', 'Kelurahan Google Kandidat',
    'Rekomendasi Kota (sementara)', 'Status Validasi', 'Link Google Maps'
]

writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator='\n')
writer.writeheader()

for rec in RECORDS:
    alamat, kota = rec['Alamat Asli'], rec['Kota Asli']
    query_info = buat_satu_query(alamat, kota)
    cache = {}

    def capture_get(*args, **kwargs):
        resp = original_get(*args, **kwargs)
        try:
            cache['data'] = resp.json()
        except ValueError:
            cache['data'] = {}
        return resp

    try:
        with patch('services.geocoding_service.requests.get', side_effect=capture_get):
            with redirect_stdout(io.StringIO()):
                result = service.geocode(alamat, kota)
    except Exception as exc:
        result = {'status': 'FAILED', 'error': type(exc).__name__ + ': ' + str(exc)}

    data = cache.get('data', {})
    status_api = data.get('status', 'TIDAK ADA RESPONS')
    chosen = None
    if result.get('status') == 'SUCCESS':
        for candidate in data.get('results', []):
            location = candidate.get('geometry', {}).get('location', {})
            if location.get('lat') == result.get('latitude') and location.get('lng') == result.get('longitude'):
                chosen = candidate
                break
    if chosen is None and data.get('results'):
        chosen = data['results'][0]  # diagnostik saja, tidak mengubah keputusan website

    chosen = chosen or {}
    geo = chosen.get('geometry', {})
    loc = geo.get('location', {})
    parts = chosen.get('address_components', [])
    type_to_names = {}
    for part in parts:
        for t in part.get('types', []):
            type_to_names.setdefault(t, []).append(part.get('long_name', ''))

    kel_candidates = set()
    kec_candidates = set()
    # Cermati hanya komponen administratif, bukan nama jalan/bangunan.
    for part in parts:
        types = part.get('types', [])
        if not any(t in types for t in ('administrative_area_level_3', 'administrative_area_level_4', 'sublocality', 'sublocality_level_1', 'sublocality_level_2')):
            continue
        name = norm(part.get('long_name', ''))
        for prefix in ('kelurahan ', 'kecamatan ', 'kel ', 'kec '):
            if name.startswith(prefix):
                name = name[len(prefix):]
        if name in KEL_TO_KEC:
            kel_candidates.add(name)
        if name in KECAMATAN:
            kec_candidates.add(name)

    kel = next(iter(kel_candidates)) if len(kel_candidates) == 1 else None
    kec = next(iter(kec_candidates)) if len(kec_candidates) == 1 else None
    if kel:
        kec_induk = norm(KEL_TO_KEC[kel])
        if kec and kec != kec_induk:
            kec = None
        else:
            kec = kec_induk

    lat = result.get('latitude') if result.get('status') == 'SUCCESS' else loc.get('lat')
    lng = result.get('longitude') if result.get('status') == 'SUCCESS' else loc.get('lng')
    pip = ''
    if lat is not None and lng is not None:
        try:
            pip = 'DALAM' if service.cek_wilayah(float(lat), float(lng)) else 'LUAR'
        except (TypeError, ValueError):
            pip = 'TIDAK DAPAT DIPERIKSA'

    partial = chosen.get('partial_match', False) if chosen else ''
    accuracy = geo.get('location_type', '')
    result_status = result.get('status', '')
    if result_status != 'SUCCESS' or not chosen:
        validation = 'PERLU CEK - GEOCODING GAGAL'
    elif pip != 'DALAM':
        validation = 'PERLU CEK - PIP LUAR'
    elif not kel:
        validation = 'PERLU CEK - KELURAHAN GOOGLE TIDAK PASTI'
    elif partial or accuracy not in ('ROOFTOP', 'RANGE_INTERPOLATED'):
        validation = 'PERLU CEK - AKURASI / PARTIAL'
    else:
        validation = 'KANDIDAT ADMINISTRASI - VERIFIKASI ALAMAT'

    recommended = ''
    if kel and kec and pip == 'DALAM' and result_status == 'SUCCESS':
        recommended = f"KOTA MALANG, {KECAMATAN[kec].upper()}, {KEL_DISPLAY[kel].upper()}"

    compact_parts = '; '.join(part.get('long_name', '') + ' (' + '/'.join(part.get('types', [])) + ')' for part in parts)
    row = {
        **rec,
        'Query Akhir': query_info.get('Query Akhir', ''),
        'Kelurahan Deteksi': query_info.get('Kelurahan Deteksi', ''),
        'Kecamatan Deteksi': query_info.get('Kecamatan Deteksi', ''),
        'Catatan Query': query_info.get('Catatan', ''),
        'Status Website': result_status,
        'Error Website': result.get('error', ''),
        'Status API': status_api,
        'Alamat Google Maps': chosen.get('formatted_address', ''),
        'Latitude': lat,
        'Longitude': lng,
        'Akurasi': accuracy,
        'Partial Match': partial,
        'PIP': pip,
        'Komponen Google Maps': compact_parts,
        'Kecamatan Google Kandidat': KECAMATAN[kec] if kec else '',
        'Kelurahan Google Kandidat': KEL_DISPLAY[kel] if kel else '',
        'Rekomendasi Kota (sementara)': recommended,
        'Status Validasi': validation,
        'Link Google Maps': f'https://www.google.com/maps?q={lat},{lng}' if lat is not None and lng is not None else '',
    }
    writer.writerow({key: row.get(key, '') for key in FIELDS})
    print(f"Diproses {rec['No']}/49: {rec['No Resi']} -> {result_status}", file=sys.stderr, flush=True)
