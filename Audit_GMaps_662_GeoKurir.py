"""Audit 662 alamat GeoKurir via Google Maps Geocoding API (jalankan dari root webgeokurir).

Instalasi: pip install openpyxl requests shapely
Jalankan: python audit_gmaps_662.py --input "Input_662_GeoKurir.xlsx"
Dapat dijalankan ulang: baris berstatus final di output sebelumnya dilewati otomatis.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

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
]
CAND_HEADERS = [
    'No. Resi', 'Urutan Kandidat Google', 'Alamat Google', 'Kota Google',
    'Kecamatan Google', 'Kelurahan Google', 'Sumber Kecamatan', 'Sumber Kelurahan',
    'Latitude', 'Longitude', 'Location Type', 'Partial Match', 'PIP', 'Place ID'
]
FINAL_STATUSES = {'OK', 'PERLU CEK MANUAL', 'LUAR KOTA', 'TIDAK DITEMUKAN', 'INPUT KOSONG'}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '').upper())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^A-Z0-9]+', '', s)


def get_component(components, *kinds):
    for k in kinds:
        for c in components:
            if k in c.get('types', []):
                return c.get('long_name', ''), k
    return '', ''


def admin_info(result):
    cs = result.get('address_components', [])
    # Level administratif Google Indonesia dapat bervariasi. Tandai sumbernya.
    city, _ = get_component(cs, 'administrative_area_level_2', 'locality')
    kec, kec_src = get_component(cs, 'administrative_area_level_3')
    kel, kel_src = get_component(cs, 'administrative_area_level_4')
    if not kec:
        kec, kec_src = get_component(cs, 'sublocality_level_1')
    if not kel:
        kel, kel_src = get_component(cs, 'sublocality_level_2', 'sublocality_level_3')
    return city, kec, kel, kec_src, kel_src


def open_polygon():
    geojson = BASE / 'data' / 'batas_kota_malang.geojson'
    if not geojson.exists():
        raise FileNotFoundError(f'File polygon tidak ada: {geojson}')
    with geojson.open(encoding='utf-8') as f:
        data = json.load(f)
    if data.get('type') == 'FeatureCollection':
        geoms = [shape(item['geometry']) for item in data.get('features', [])]
        if len(geoms) != 1:
            raise ValueError('Polygon harus berisi satu fitur Kota Malang seperti pada GeoKurir')
        return geoms[0]
    return shape(data['geometry'] if data.get('type') == 'Feature' else data)


def setup_workbook(output, input_path):
    if output.exists():
        wb = load_workbook(output)
        return wb, wb['Hasil Geocoding'], wb['Semua Kandidat']
    source = load_workbook(input_path, read_only=True, data_only=True)
    sh_in = source.active
    rows = list(sh_in.iter_rows(min_row=2, values_only=True))
    wb = Workbook()
    sh = wb.active
    sh.title = 'Hasil Geocoding'
    sh.append(HEADERS)
    for r in rows:
        sh.append([*list(r[:6]), *([None] * (len(HEADERS) - 6))])
    cand = wb.create_sheet('Semua Kandidat')
    cand.append(CAND_HEADERS)
    info = wb.create_sheet('Petunjuk')
    for row in [
        ['Audit Geocoding 662 Data GeoKurir Malang'],
        ['Sumber', str(input_path)],
        ['Metode', 'Google Maps Geocoding API + buat_satu_query() GeoKurir + PIP Kota Malang'],
        ['Perhatian', 'PIP DALAM hanya memastikan koordinat hasil Google di polygon, bukan ketepatan rumah/kelurahan.'],
        ['Rekomendasi Kota', 'KANDIDAT, bukan penggantian otomatis Kota Asli. Periksa hasil partial_match, rooftop dan administrasi.'],
        ['Status Evaluasi', 'OK = komponen wilayah jelas dan cocok; PERLU CEK MANUAL = ambigu/konflik; LUAR KOTA = hasil di luar polygon.'],
        ['Melanjutkan', 'Jalankan ulang perintah yang sama untuk melanjutkan hasil setelah terputus.'],
    ]:
        info.append(row)
    for sheet in [sh, cand]:
        sheet.freeze_panes = 'G2' if sheet == sh else 'C2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = PatternFill('solid', fgColor='17365D')
            cell.font = Font(bold=True, color='FFFFFF')
            cell.alignment = Alignment(wrap_text=True, vertical='center')
        sheet.row_dimensions[1].height = 32
        for j in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(j)].width = 18
    for col in ['E','G','H','N','W']:
        sh.column_dimensions[col].width = 45
    sh.column_dimensions['D'].width = 25
    cand.column_dimensions['C'].width = 65
    info.column_dimensions['A'].width = 25
    info.column_dimensions['B'].width = 110
    wb.save(output)
    return wb, sh, cand


def load_config():
    try:
        from config import Config
        from services.query import buat_satu_query
    except ImportError as e:
        raise RuntimeError('Tempatkan script di folder root webgeokurir yang berisi config.py dan services/query.py') from e
    api_key = getattr(Config, 'GOOGLE_MAPS_API_KEY', None)
    if not api_key:
        raise RuntimeError('Config.GOOGLE_MAPS_API_KEY kosong. Periksa konfigurasi aplikasi.')
    return api_key, buat_satu_query


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='Input_662_GeoKurir.xlsx')
    ap.add_argument('--output', default='Hasil_Geocoding_GMaps_662_GeoKurir.xlsx')
    ap.add_argument('--delay', type=float, default=0.15)
    ap.add_argument('--limit', type=int, default=0, help='Jumlah request baru maksimal (0=semua)')
    ap.add_argument('--save-every', type=int, default=10)
    args = ap.parse_args()
    input_path = Path(args.input).resolve()
    output = Path(args.output).resolve()
    if not input_path.exists():
        sys.exit(f'TIDAK ADA FILE INPUT: {input_path}')
    api_key, buat_satu_query = load_config()
    polygon = open_polygon()
    minx, miny, maxx, maxy = polygon.bounds
    bounds = f'{miny},{minx}|{maxy},{maxx}'
    wb, sh, candidates = setup_workbook(output, input_path)
    session = requests.Session()
    processed = 0
    print(f'Input: {input_path.name} | Baris: {sh.max_row-1} | Hasil: {output.name}', flush=True)

    try:
        for row in range(2, sh.max_row + 1):
            current_status = str(sh.cell(row, 21).value or '')
            if current_status in FINAL_STATUSES:
                continue
            if args.limit and processed >= args.limit:
                break
            noresi = str(sh.cell(row, 4).value or '').strip()
            alamat = str(sh.cell(row, 5).value or '').strip()
            kota = str(sh.cell(row, 6).value or '').strip()
            if not alamat:
                sh.cell(row, 21, 'INPUT KOSONG')
                sh.cell(row, 22, 'PERLU CEK MANUAL')
                continue
            try:
                detail = buat_satu_query(alamat, kota)
                query = detail.get('Query Akhir', '') if isinstance(detail, dict) else str(detail)
                if not query:
                    raise ValueError('Query Akhir kosong')
                sh.cell(row, 7, query)
                print(f'[{row-1}/{sh.max_row-1}] {noresi} | {query[:90]}', flush=True)
                response = session.get(
                    'https://maps.googleapis.com/maps/api/geocode/json',
                    params={'address': query, 'bounds': bounds, 'components': 'country:ID',
                            'region': 'id', 'key': api_key}, timeout=(5, 30)
                )
                response.raise_for_status()
                payload = response.json()
                status = payload.get('status', 'UNKNOWN_ERROR')
                if status in {'OVER_QUERY_LIMIT', 'OVER_DAILY_LIMIT', 'REQUEST_DENIED', 'INVALID_REQUEST'}:
                    raise RuntimeError(f'Google API menghentikan proses: {status} - {payload.get("error_message", "")}')
                if status == 'ZERO_RESULTS':
                    sh.cell(row, 21, 'TIDAK DITEMUKAN')
                    sh.cell(row, 22, 'PERLU CEK MANUAL')
                    sh.cell(row, 23, 'Google Maps tidak mengembalikan kandidat')
                    processed += 1
                    continue
                if status != 'OK':
                    sh.cell(row, 23, f'API status {status}; akan dicoba ulang')
                    print(f'PERINGATAN: {status}; berhenti agar tidak mengulang request tanpa kendali', flush=True)
                    break
                results = payload.get('results', [])
                selected = None
                details = []
                for index, result in enumerate(results, 1):
                    loc = result.get('geometry', {}).get('location', {})
                    lat, lon = loc.get('lat'), loc.get('lng')
                    inside = lat is not None and lon is not None and polygon.covers(Point(lon, lat))
                    city, kec, kel, kec_src, kel_src = admin_info(result)
                    cand = [noresi, index, result.get('formatted_address'), city, kec, kel,
                            kec_src, kel_src, lat, lon, result.get('geometry', {}).get('location_type'),
                            str(bool(result.get('partial_match', False))),
                            'DALAM' if inside else 'LUAR', result.get('place_id')]
                    candidates.append(cand)
                    details.append((result, inside, city, kec, kel, kec_src, kel_src, lat, lon))
                    # Pertahankan urutan Google: kandidat pertama yang berada di polygon.
                    if selected is None and inside:
                        selected = details[-1]
                if selected is None and details:
                    selected = details[0]
                if selected is None:
                    sh.cell(row, 21, 'TIDAK DITEMUKAN')
                    sh.cell(row, 22, 'PERLU CEK MANUAL')
                    processed += 1
                    continue
                result, inside, city, kec, kel, kec_src, kel_src, lat, lon = selected
                geometry_type = result.get('geometry', {}).get('location_type', '')
                partial = bool(result.get('partial_match', False))
                selected_values = [
                    result.get('formatted_address', ''), city, kec, kel, kec_src, kel_src,
                    f'KOTA MALANG, {kec.upper()}, {kel.upper()}' if inside and kec and kel else '',
                    lat, lon, geometry_type, 'YA' if partial else 'TIDAK',
                    'DALAM' if inside else 'LUAR', len(results),
                ]
                for column, value in enumerate(selected_values, start=8):
                    sh.cell(row, column, value)
                sh.cell(row, 24, f'https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}')
                sh.cell(row, 25, result.get('place_id'))
                note = []
                if not inside:
                    decision = 'PERLU CEK MANUAL'
                    status_final = 'LUAR KOTA'
                    note.append('Tidak ada kandidat di dalam polygon Kota Malang')
                else:
                    status_final = 'OK'
                    decision = 'OK'
                    if partial:
                        note.append('Google partial_match=True')
                    if geometry_type != 'ROOFTOP':
                        note.append('Koordinat bukan ROOFTOP / tidak presisi ke rumah')
                    if not (kec and kel):
                        note.append('Komponen kelurahan/kecamatan Google tidak lengkap')
                    if kec_src != 'administrative_area_level_3' or kel_src != 'administrative_area_level_4':
                        note.append('Periksa klasifikasi komponen administratif Google')
                    parts = [p.strip() for p in kota.split(',')]
                    if len(parts) >= 3:
                        if kec and norm(parts[1]) != norm(kec):
                            note.append('Kecamatan Google berbeda dengan Kota Asli')
                        if kel and norm(parts[2]) != norm(kel):
                            note.append('Kelurahan Google berbeda dengan Kota Asli')
                    if len(results) > 1:
                        note.append('Ada lebih dari satu kandidat Google, lihat sheet Semua Kandidat')
                    if note:
                        decision = 'PERLU CEK MANUAL'
                sh.cell(row, 21, status_final)
                sh.cell(row, 22, decision)
                sh.cell(row, 23, '; '.join(note) if note else 'Kecamatan dan kelurahan cocok dengan komponen Google')
                processed += 1
                if processed % args.save_every == 0:
                    wb.save(output)
                    print(f'  -> Disimpan: {processed} request baru', flush=True)
                time.sleep(max(0, args.delay))
            except (requests.RequestException, ValueError, RuntimeError) as e:
                sh.cell(row, 23, f'ERROR / BELUM DIPROSES: {str(e)[:250]}')
                wb.save(output)
                print(f'BERHENTI pada resi {noresi}: {e}', file=sys.stderr, flush=True)
                break
    except KeyboardInterrupt:
        print('Dihentikan oleh pengguna. Menyimpan progres...', flush=True)
    finally:
        wb.save(output)
        session.close()
    print(f'SELESAI / PROGRES TERSIMPAN: {output}', flush=True)
    print('PENTING: rekomendasi administratif dari Google adalah kandidat, bukan kepastian lokasi tujuan.', flush=True)


if __name__ == '__main__':
    main()
