"""Audit geocoding GeoKurir V2: Google Geocoding API + validasi PIP + evaluasi kandidat.

Jalankan dari root proyek GeoKurir (folder config.py, services/query.py, data/).

Uji ulang 10 hasil lama TANPA request Google baru:
    python Audit_GMaps_662_GeoKurir_V2.py --input Input_662_GeoKurir.xlsx \
      --previous Hasil_Geocoding_GMaps_662_GeoKurir.xlsx --recheck-only

Lanjut geocoding (menggunakan hasil 10 lama, tanpa request ulang):
    python Audit_GMaps_662_GeoKurir_V2.py --input Input_662_GeoKurir.xlsx \
      --previous Hasil_Geocoding_GMaps_662_GeoKurir.xlsx --limit 10

Perintah yang sama tanpa --limit untuk semua sisa data. Jangan gunakan --previous
jika output V2 telah dibuat; program akan melanjutkan output V2 secara otomatis.

CATATAN: Semua hasil administrasi Google adalah KANDIDAT, bukan kebenaran pasti.
Program TIDAK mengubah dataset asli, web, ataupun database GeoKurir.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from shapely.geometry import Point, shape

BASE = Path(__file__).resolve().parent
HEADERS = [
    'No.', 'Tanggal Dataset', 'Shift', 'No. Resi', 'Alamat Asli', 'Kota Asli',
    'Query GeoKurir', 'Alamat Google Maps', 'Kota Google', 'Kecamatan Google',
    'Kelurahan Google', 'Sumber Kecamatan', 'Sumber Kelurahan',
    'Rekomendasi Kota (Kandidat)', 'Latitude', 'Longitude', 'Location Type',
    'Partial Match', 'PIP Kota Malang', 'Jumlah Kandidat Google',
    'Status Geocoding', 'Status Evaluasi', 'Catatan', 'Google Maps', 'Place ID',
    'Urutan Kandidat Terpilih', 'Skor Kecocokan', 'Kecamatan Ternormalisasi',
    'Kelurahan Ternormalisasi', 'Kecamatan dari Alamat', 'Kelurahan dari Alamat',
    'Kesesuaian Wilayah', 'Tingkat Ketelitian',
]
CAND_HEADERS = [
    'No. Resi', 'Urutan Kandidat Google', 'Alamat Google', 'Kota Google',
    'Kecamatan Google', 'Kelurahan Google', 'Sumber Kecamatan', 'Sumber Kelurahan',
    'Latitude', 'Longitude', 'Location Type', 'Partial Match', 'PIP', 'Place ID',
    'Skor Kecocokan', 'Catatan Kandidat', 'Terpilih',
]
DONE = {'OK', 'LUAR KOTA', 'TIDAK DITEMUKAN', 'INPUT KOSONG'}
DISTRICTS = {'KLOJEN', 'BLIMBING', 'LOWOKWARU', 'SUKUN', 'KEDUNGKANDANG'}
COMMON = {
    'JALAN', 'JL', 'JLN', 'GANG', 'GG', 'NO', 'NOMOR', 'RT', 'RW', 'KEL',
    'KELURAHAN', 'KEC', 'KECAMATAN', 'KOTA', 'MALANG', 'JAWA', 'TIMUR',
    'INDONESIA', 'PROVINSI', 'DEPAN', 'BELAKANG', 'SAMPING', 'RUMAH', 'DI',
    'THE', 'DAN', 'PERUM', 'PERUMAHAN', 'BLOK', 'DESA', 'DUSUN', 'DS', 'DK',
}


def normalized(value):
    s = unicodedata.normalize('NFKD', str(value or '').upper())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\b(?:KECAMATAN|KEC|KELURAHAN|KEL|DESA)\.?\s+', ' ', s)
    return re.sub(r'[^A-Z0-9]+', '', s)


def clean_admin(value):
    s = unicodedata.normalize('NFKD', str(value or '').upper())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'^(?:(?:KECAMATAN|KEC|KELURAHAN|KEL|DESA)\.?\s+)+', '', s)
    return re.sub(r'\s+', ' ', s).strip(' ,.-')


def admin_equal(a, b):
    return bool(a and b) and normalized(a) == normalized(b)


def tokens(s):
    text = unicodedata.normalize('NFKD', str(s or '').upper())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    found = re.findall(r'[A-Z]{2,}|\d+[A-Z]?', text)
    return {x for x in found if x not in COMMON and (len(x) >= 3 or re.match(r'^\d', x))}


def fetch_component(components, *levels):
    for level in levels:
        for component in components:
            if level in component.get('types', []):
                return component.get('long_name', ''), level
    return '', ''


def administrative(result):
    components = result.get('address_components', [])
    city, _ = fetch_component(components, 'administrative_area_level_2', 'locality')
    kec, kec_source = fetch_component(components, 'administrative_area_level_3')
    kel, kel_source = fetch_component(components, 'administrative_area_level_4')
    if not kec:
        kec, kec_source = fetch_component(components, 'sublocality_level_1')
    if not kel:
        kel, kel_source = fetch_component(components, 'sublocality_level_2', 'sublocality_level_3')
    return city, kec, kel, kec_source, kel_source


def guessed_from_address(detail):
    if not isinstance(detail, dict):
        return '', ''
    sumber = str(detail.get('Sumber Wilayah', '')).upper()
    # Deteksi dari kolom Kota tidak boleh diperlakukan sebagai bukti dari alamat.
    if 'KOTA' in sumber and 'ALAMAT' not in sumber:
        return '', ''
    return (clean_admin(detail.get('Kecamatan Deteksi', '')),
            clean_admin(detail.get('Kelurahan Deteksi', '')))


def parse_kota(value):
    parts = [clean_admin(p) for p in str(value or '').split(',')]
    return (parts[1] if len(parts) >= 2 else '',
            parts[2] if len(parts) >= 3 else '')


def polygon_load():
    path = BASE / 'data' / 'batas_kota_malang.geojson'
    with path.open(encoding='utf-8') as handle:
        payload = json.load(handle)
    if payload.get('type') == 'FeatureCollection':
        features = payload.get('features', [])
        if len(features) != 1:
            raise ValueError('Dibutuhkan tepat satu fitur polygon Kota Malang')
        return shape(features[0]['geometry'])
    return shape(payload['geometry'] if payload.get('type') == 'Feature' else payload)


def score_candidate(c, address, original_kota, detected_kec='', detected_kel=''):
    score, notes = 0, []
    if not c['inside']:
        score -= 1000
        notes.append('PIP luar')
    if c['city'] and 'MALANG' not in normalized(c['city']):
        score -= 100
        notes.append('Nama kota Google bukan Kota Malang')
    typ = str(c['type'] or '').upper()
    score += {'ROOFTOP': 25, 'RANGE_INTERPOLATED': 17,
              'GEOMETRIC_CENTER': 7, 'APPROXIMATE': 1}.get(typ, 0)
    if c['partial']:
        score -= 12
    a_tokens = tokens(address)
    g_tokens = tokens(c['address'])
    common = a_tokens & g_tokens
    score += min(35, len(common) * 5)
    if a_tokens and not common:
        score -= 20
        notes.append('Tidak ada token alamat yang sama')
    kec0, kel0 = parse_kota(original_kota)
    kec = clean_admin(c['kec'])
    kel = clean_admin(c['kel'])
    # Nama wilayah eksplisit dari alamat lebih penting daripada kolom Kota asli.
    if detected_kec and kec:
        score += 30 if admin_equal(detected_kec, kec) else -35
        if not admin_equal(detected_kec, kec):
            notes.append('Kecamatan Google bertentangan dengan deteksi alamat')
    if detected_kel and kel:
        score += 35 if admin_equal(detected_kel, kel) else -40
        if not admin_equal(detected_kel, kel):
            notes.append('Kelurahan Google bertentangan dengan deteksi alamat')
    # Kota asli bisa salah; beri bobot rendah agar tidak mendominasi pilihan.
    if kec0 and kec and admin_equal(kec0, kec):
        score += 4
    if kel0 and kel and admin_equal(kel0, kel):
        score += 4
    if normalized(kec) not in DISTRICTS:
        score -= 20
        notes.append('Kecamatan Google tidak dikenali sebagai 5 kecamatan')
    if not kel:
        score -= 15
        notes.append('Kelurahan tidak tersedia dari Google')
    return score, notes


def candidate_from_result(result, index, polygon):
    loc = result.get('geometry', {}).get('location', {})
    lat, lon = loc.get('lat'), loc.get('lng')
    inside = bool(lat is not None and lon is not None and
                  polygon.covers(Point(float(lon), float(lat))))
    city, kec, kel, ks, ls = administrative(result)
    return dict(index=index, address=result.get('formatted_address', ''),
                city=city, kec=kec, kel=kel, kec_source=ks, kel_source=ls,
                lat=lat, lon=lon, type=result.get('geometry', {}).get('location_type', ''),
                partial=bool(result.get('partial_match', False)), inside=inside,
                place_id=result.get('place_id', ''))


def candidate_from_excel(row):
    def val(i):
        return row[i] if len(row) > i else None
    return dict(index=int(val(1) or 1), address=val(2) or '', city=val(3) or '',
                kec=val(4) or '', kel=val(5) or '',
                kec_source=val(6) or '', kel_source=val(7) or '',
                lat=val(8), lon=val(9), type=val(10) or '',
                partial=str(val(11) or '').upper() in {'TRUE', 'YA', '1'},
                inside=str(val(12) or '').upper() == 'DALAM', place_id=val(13) or '')


def candidate_excel(noresi, c, selected=False):
    return [noresi, c['index'], c['address'], c['city'], c['kec'], c['kel'],
            c['kec_source'], c['kel_source'], c['lat'], c['lon'], c['type'],
            'YA' if c['partial'] else 'TIDAK', 'DALAM' if c['inside'] else 'LUAR',
            c['place_id'], c.get('score', 0), '; '.join(c.get('notes', [])),
            'YA' if selected else 'TIDAK']


def selected_evaluation(candidates, address, kota, detail):
    detected_kec, detected_kel = guessed_from_address(detail)
    for c in candidates:
        c['score'], c['notes'] = score_candidate(c, address, kota, detected_kec, detected_kel)
    ranked = sorted(candidates, key=lambda c: (-c['score'], c['index']))
    selected = ranked[0] if ranked else None
    return selected, detected_kec, detected_kel, ranked


def severity(selected, candidates, kota, det_kec, det_kel):
    if not selected:
        return 'PERLU CEK MANUAL', 'TIDAK TERSEDIA', 'TIDAK TERSEDIA', ['Tidak ada kandidat Google']
    notes = []
    if not selected['inside']:
        notes.append('Tidak ada kandidat yang terpilih di dalam polygon Kota Malang')
    if selected['city'] and 'KABUPATEN' in str(selected['city']).upper():
        notes.append('Google menyebut Kabupaten, bukan Kota Malang')
    kec = clean_admin(selected['kec'])
    kel = clean_admin(selected['kel'])
    orig_kec, orig_kel = parse_kota(kota)
    if orig_kec and kec and not admin_equal(orig_kec, kec):
        notes.append('Kecamatan Google berbeda dengan Kota asli')
    if orig_kel and kel and not admin_equal(orig_kel, kel):
        notes.append('Kelurahan Google berbeda dengan Kota asli')
    if det_kec and kec and not admin_equal(det_kec, kec):
        notes.append('Kecamatan Google berbeda dengan deteksi alamat')
    if det_kel and kel and not admin_equal(det_kel, kel):
        notes.append('Kelurahan Google berbeda dengan deteksi alamat')
    if not kec or normalized(kec) not in DISTRICTS or not kel:
        notes.append('Komponen administratif Google belum lengkap atau tidak dikenali')
    if selected['kec_source'] != 'administrative_area_level_3':
        notes.append('Sumber kecamatan Google alternatif')
    if selected['kel_source'] != 'administrative_area_level_4':
        notes.append('Sumber kelurahan Google alternatif')
    if selected['partial']:
        notes.append('Google partial_match=True')
    if selected['type'] != 'ROOFTOP':
        notes.append('Koordinat bukan ROOFTOP; ketelitian alamat terbatas')
    if len(candidates) > 1:
        runnerup = sorted(candidates, key=lambda x: (-x['score'], x['index']))[1]
        if selected['score'] - runnerup['score'] <= 10:
            notes.append('Skor kandidat teratas berdekatan; lihat Semua Kandidat')
    wilayah = 'SESUAI' if not any('berbeda' in n or 'tidak dikenali' in n for n in notes) else 'KONFLIK/AMBIGU'
    ketelitian = ('PERKIRAAN/LEVEL JALAN' if selected['type'] != 'ROOFTOP' or selected['partial']
                  else 'ROOFTOP (perlu cocokkan alamat)')
    status = 'OK - PERLU SAMPEL' if not notes else 'PERLU CEK MANUAL'
    return status, wilayah, ketelitian, notes


def ensure_book(input_path, output, previous):
    if output.exists():
        wb = load_workbook(output)
    elif previous and previous.exists():
        wb = load_workbook(previous)
    else:
        source = load_workbook(input_path, read_only=True, data_only=True)
        wb = Workbook()
        ws = wb.active
        ws.title = 'Hasil Geocoding'
        ws.append(HEADERS)
        for row in source.active.iter_rows(min_row=2, values_only=True):
            if not any(v is not None for v in row):
                continue
            ws.append(list(row[:6]) + [None] * (len(HEADERS) - 6))
        csh = wb.create_sheet('Semua Kandidat')
        csh.append(CAND_HEADERS)
        wb.create_sheet('Petunjuk')
    sh, cand = wb['Hasil Geocoding'], wb['Semua Kandidat']
    source = load_workbook(input_path, read_only=True, data_only=True)
    original_rows = [r for r in source.active.iter_rows(min_row=2, values_only=True)
                     if any(v is not None for v in r)]
    if sh.max_row - 1 != len(original_rows):
        raise ValueError('Output lama tidak sesuai input: jumlah baris berbeda. Gunakan output baru.')
    for pos, source_row in enumerate(original_rows, 2):
        if str(sh.cell(pos, 4).value or '').strip() != str(source_row[3] or '').strip():
            raise ValueError(f'Output lama tidak cocok dengan Input pada baris {pos}; hentikan agar data tidak tertukar.')
    for col, header in enumerate(HEADERS, 1):
        sh.cell(1, col, header)
    for col, header in enumerate(CAND_HEADERS, 1):
        cand.cell(1, col, header)
    info = wb['Petunjuk']
    info.delete_rows(1, info.max_row)
    for r in [
        ['Audit GeoKurir V2', 'Ranking kandidat adalah heuristik, bukan kepastian alamat/kelurahan.'],
        ['Metode', 'Single Query GeoKurir + Google Geocoding API + PIP polygon Kota Malang'],
        ['Output', 'Seluruh data asli dipertahankan; Kota rekomendasi adalah KANDIDAT'],
        ['Status', 'OK - PERLU SAMPEL = hasil tampak cocok tetapi tetap perlu sampling; PERLU CEK MANUAL = ambiguitas'],
        ['PIP', 'DALAM hanya lokasi hasil Google dalam polygon, bukan verifikasi alamat tujuan'],
        ['Kec/Kel', 'Komponen administratif Google dapat tidak lengkap atau tidak akurat'],
        ['Recheck', '--recheck-only memakai kandidat Excel lama TANPA Google API'],
        ['Resume', 'Output V2 yang sudah ada dipakai lagi; kandidat lama dievaluasi ulang tanpa API'],
        ['Perkiraan', 'Non-ROOFTOP dan partial_match tidak boleh dianggap koordinat rumah presisi'],
    ]:
        info.append(r)
    for ws, freeze in [(sh, 'G2'), (cand, 'C2')]:
        ws.freeze_panes = freeze
        ws.auto_filter.ref = f'A1:{get_column_letter(ws.max_column)}{ws.max_row}'
        for cell in ws[1]:
            cell.fill = PatternFill('solid', fgColor='183153')
            cell.font = Font(bold=True, color='FFFFFF')
            cell.alignment = Alignment(vertical='center', wrap_text=True)
        ws.row_dimensions[1].height = 36
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = 21
    for letter in ['E', 'G', 'H', 'N', 'W']:
        sh.column_dimensions[letter].width = 46
    sh.column_dimensions['D'].width = 25
    cand.column_dimensions['C'].width = 62
    cand.column_dimensions['P'].width = 52
    info.column_dimensions['A'].width = 20
    info.column_dimensions['B'].width = 100
    return wb, sh, cand


def record_result(sh, row, candidates, detail):
    address = str(sh.cell(row, 5).value or '')
    kota = str(sh.cell(row, 6).value or '')
    chosen, det_kec, det_kel, ranking = selected_evaluation(candidates, address, kota, detail)
    if not chosen:
        sh.cell(row, 21, 'TIDAK DITEMUKAN')
        sh.cell(row, 22, 'PERLU CEK MANUAL')
        sh.cell(row, 23, 'Google tidak mengembalikan kandidat')
        return None
    rank_status, wilayah, precision, notes = severity(chosen, candidates, kota, det_kec, det_kel)
    inside = chosen['inside']
    status = 'OK' if inside else 'LUAR KOTA'
    kec, kel = clean_admin(chosen['kec']), clean_admin(chosen['kel'])
    rec = (f'KOTA MALANG, {kec}, {kel}' if inside and normalized(kec) in DISTRICTS and kel
           else '')
    loc_url = ''
    if chosen['lat'] is not None and chosen['lon'] is not None:
        loc_url = ('https://www.google.com/maps/search/?api=1&query='
                   + quote(f"{chosen['lat']},{chosen['lon']}"))
    values = {
        8: chosen['address'], 9: chosen['city'], 10: chosen['kec'],
        11: chosen['kel'], 12: chosen['kec_source'], 13: chosen['kel_source'],
        14: rec, 15: chosen['lat'], 16: chosen['lon'], 17: chosen['type'],
        18: 'YA' if chosen['partial'] else 'TIDAK',
        19: 'DALAM' if inside else 'LUAR', 20: len(candidates),
        21: status, 22: rank_status if inside else 'PERLU CEK MANUAL',
        23: '; '.join(notes) if notes else 'Tidak ada konflik yang terdeteksi; tetap lakukan sampling',
        24: loc_url, 25: chosen['place_id'], 26: chosen['index'],
        27: chosen['score'], 28: kec, 29: kel,
        30: det_kec, 31: det_kel, 32: wilayah, 33: precision,
    }
    for col, val in values.items():
        sh.cell(row, col, val)
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='Input_662_GeoKurir.xlsx')
    parser.add_argument('--output', default='Hasil_Geocoding_GMaps_662_GeoKurir_V2.xlsx')
    parser.add_argument('--previous', default='', help='Excel audit V1 untuk impor kandidat lama')
    parser.add_argument('--recheck-only', action='store_true', help='Hanya evaluasi kandidat tersimpan, tanpa API')
    parser.add_argument('--limit', type=int, default=0, help='Maksimum request Google baru (0 = semua)')
    parser.add_argument('--save-every', type=int, default=10)
    parser.add_argument('--delay', type=float, default=0.15)
    args = parser.parse_args()
    input_path = Path(args.input).resolve()
    output = Path(args.output).resolve()
    previous = Path(args.previous).resolve() if args.previous else None
    if not input_path.is_file():
        sys.exit(f'File input tidak ditemukan: {input_path}')
    if previous and not previous.is_file() and not output.exists():
        sys.exit(f'File hasil lama tidak ditemukan: {previous}')
    if output == input_path or (previous and output == previous):
        sys.exit('Gunakan nama output berbeda agar file asli tidak tertimpa.')
    if args.limit < 0 or args.save_every < 1:
        sys.exit('--limit harus >=0 dan --save-every harus >=1')
    wb, sh, csh = ensure_book(input_path, output, previous)
    try:
        from services.query import buat_satu_query
    except ImportError as exc:
        raise RuntimeError('Simpan script di root proyek yang memiliki services/query.py') from exc
    polygon = polygon_load()
    minx, miny, maxx, maxy = polygon.bounds
    bounds = f'{miny},{minx}|{maxy},{maxx}'
    grouped = defaultdict(list)
    for excel_row in csh.iter_rows(min_row=2, values_only=True):
        if excel_row[0]:
            grouped[str(excel_row[0]).strip()].append(candidate_from_excel(excel_row))
    api_key = None
    if not args.recheck_only:
        from config import Config
        api_key = getattr(Config, 'GOOGLE_MAPS_API_KEY', None)
        if not api_key:
            sys.exit('Config.GOOGLE_MAPS_API_KEY kosong')
    session = requests.Session()
    new_requests = 0
    reused = 0
    refreshed = []
    print(f'Input {sh.max_row-1} data | kandidat tersimpan {sum(map(len, grouped.values()))}', flush=True)
    try:
        for row in range(2, sh.max_row + 1):
            noresi = str(sh.cell(row, 4).value or '').strip()
            alamat = str(sh.cell(row, 5).value or '').strip()
            kota = str(sh.cell(row, 6).value or '').strip()
            if not alamat:
                sh.cell(row, 21, 'INPUT KOSONG')
                sh.cell(row, 22, 'PERLU CEK MANUAL')
                sh.cell(row, 23, 'Alamat asli kosong')
                continue
            # Query wajib memakai fungsi asli GeoKurir, bukan dibangun ulang.
            detail = buat_satu_query(alamat, kota)
            query = detail.get('Query Akhir', '') if isinstance(detail, dict) else str(detail)
            if not query:
                raise ValueError(f'Query Akhir kosong pada {noresi}')
            sh.cell(row, 7, query)
            candidates = grouped.get(noresi, [])
            if candidates:
                reused += 1
                record_result(sh, row, candidates, detail)
                refreshed.append(noresi)
                continue
            if sh.cell(row, 21).value in DONE:
                continue  # termasuk ZERO_RESULTS hasil V1: jangan request ulang diam-diam
            if args.recheck_only or (args.limit and new_requests >= args.limit):
                continue
            print(f'[{row-1}/{sh.max_row-1}] {noresi} | {query[:90]}', flush=True)
            try:
                response = session.get(
                    'https://maps.googleapis.com/maps/api/geocode/json',
                    params={'address': query, 'bounds': bounds, 'components': 'country:ID',
                            'region': 'id', 'key': api_key}, timeout=(5, 30))
                response.raise_for_status()
                payload = response.json()
                status = payload.get('status', 'UNKNOWN_ERROR')
                if status in {'REQUEST_DENIED', 'OVER_QUERY_LIMIT', 'OVER_DAILY_LIMIT', 'INVALID_REQUEST'}:
                    raise RuntimeError(f'Google API: {status} - {payload.get("error_message", "")}')
                if status not in {'OK', 'ZERO_RESULTS'}:
                    raise RuntimeError(f'Google API sementara: {status}')
                if status == 'ZERO_RESULTS':
                    sh.cell(row, 21, 'TIDAK DITEMUKAN')
                    sh.cell(row, 22, 'PERLU CEK MANUAL')
                    sh.cell(row, 23, 'Google ZERO_RESULTS')
                    new_requests += 1
                    continue
                candidates = [candidate_from_result(res, i, polygon)
                              for i, res in enumerate(payload.get('results', []), 1)]
                chosen = record_result(sh, row, candidates, detail)
                for candidate in candidates:
                    csh.append(candidate_excel(noresi, candidate, candidate is chosen))
                grouped[noresi] = candidates
                new_requests += 1
                if new_requests % args.save_every == 0:
                    wb.save(output)
                    print(f'  Tersimpan {new_requests} request baru', flush=True)
                time.sleep(max(0, args.delay))
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                message = str(exc)
                # Avoid echoing sensitive API key if included in an exception URL.
                if api_key:
                    message = message.replace(api_key, '[API_KEY_REDACTED]')
                sh.cell(row, 23, f'BELUM SELESAI: {message[:180]}')
                print(f'BERHENTI pada {noresi}: {message[:180]}', file=sys.stderr)
                break
    except KeyboardInterrupt:
        print('Dihentikan pengguna; menyimpan progres...')
    finally:
        # Update kandidat lama agar penilaian skor dan pilihan V2 tercatat pada Excel.
        for row_idx in range(2, csh.max_row + 1):
            resi = str(csh.cell(row_idx, 1).value or '').strip()
            matching = grouped.get(resi, [])
            if not matching:
                continue
            cand_idx = int(csh.cell(row_idx, 2).value or 1)
            record = next((c for c in matching if c['index'] == cand_idx), None)
            if record:
                for col, value in [(15, record.get('score', '')),
                                   (16, '; '.join(record.get('notes', [])))]:
                    csh.cell(row_idx, col, value)
                csh.cell(row_idx, 17, 'YA' if record['index'] == next(
                    (sh.cell(r, 26).value for r in range(2, sh.max_row+1)
                     if str(sh.cell(r, 4).value or '').strip() == resi), None) else 'TIDAK')
        wb.save(output)
        session.close()
    print(f'Selesai. Re-evaluasi tersimpan: {reused}; request baru: {new_requests}')
    print(f'Excel: {output}')
    print('PENTING: Google dan skor merupakan kandidat; validasi manual untuk konflik/partial_match.')


if __name__ == '__main__':
    main()
