"""Uji browser pada database sementara: python tests/browser_dataset_delete.py.

Memerlukan Playwright dan Chromium. Tidak menggunakan data website aktif.
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler

from test_dataset_delete import DatasetDeleteTest
from app import app


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    DatasetDeleteTest.setUpClass()
    server = None
    thread = None
    try:
        fixtures = DatasetDeleteTest()
        fixtures.setUp()
        second_target = fixtures.create_dataset('delete-second.csv')
        unprocessed = fixtures.create_dataset('unprocessed.csv', processed=False)
        server = make_server('127.0.0.1', 0, app, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1365, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                # Gunakan fallback peta bawaan agar tes tidak memerlukan layanan luar.
                page.route('**/*', lambda route: route.continue_()
                           if route.request.url.startswith(url) else route.abort())
                page.goto(url + '/hapus-dataset', wait_until='networkidle')
                checkboxes = page.locator('#table-delete-datasets-body input[type=checkbox]')
                select_all = page.locator('#select-all-delete-datasets')
                selected_count = page.locator('#delete-dataset-selection-count')
                delete_button = page.get_by_role('button', name='Hapus terpilih', exact=True)
                search = page.locator('#search-delete-dataset')
                expect(checkboxes).to_have_count(4)
                expect(delete_button).to_be_disabled()
                options = page.locator('#select-process-dashboard option')
                option_ids = options.evaluate_all('(items) => items.map(item => Number(item.value.replace("db_", ""))).sort()')
                row_ids = checkboxes.evaluate_all('(items) => items.map(item => Number(item.dataset.datasetId)).sort()')
                assert option_ids == row_ids
                expect(page.get_by_role('row').filter(has_text='unprocessed.csv')).to_contain_text('Belum diproses')

                # Pilihan individual, status sebagian, dan pilihan semua terfilter.
                page.get_by_role('checkbox', name='Pilih dataset delete-me.csv', exact=True).check()
                expect(select_all).to_have_js_property('indeterminate', True)
                expect(selected_count).to_have_text('1 dataset dipilih')
                search.fill('delete-')
                expect(checkboxes).to_have_count(2)
                select_all.check()
                expect(selected_count).to_have_text('2 dataset dipilih')
                search.fill('keep-me')
                expect(checkboxes).to_have_count(1)
                expect(checkboxes).not_to_be_checked()
                expect(selected_count).to_have_text('2 dataset dipilih')
                search.fill('tidak-ada')
                expect(select_all).to_be_disabled()
                expect(delete_button).to_be_enabled()
                search.fill('')
                expect(select_all).to_have_js_property('indeterminate', True)

                # Membatalkan konfirmasi tidak mengirim permintaan penghapusan.
                deletes = []
                page.on('request', lambda request: deletes.append(request.post_data_json)
                        if request.method == 'DELETE' else None)
                page.once('dialog', lambda dialog: dialog.dismiss())
                delete_button.click()
                assert not deletes
                expect(selected_count).to_have_text('2 dataset dipilih')
                assert len(fixtures.snapshot()['dataset']) == 4

                # Kegagalan server mempertahankan baris dan pilihan untuk dicoba lagi.
                def fail_delete(route):
                    if route.request.method == 'DELETE':
                        route.fulfill(status=500, json={'success': False, 'error': 'Gagal uji hapus massal'})
                    else:
                        route.continue_()

                page.route('**/api/datasets', fail_delete)
                page.once('dialog', lambda dialog: dialog.accept())
                delete_button.click()
                expect(page.locator('#toast-container')).to_contain_text('Gagal uji hapus massal')
                expect(delete_button).to_be_enabled()
                expect(selected_count).to_have_text('2 dataset dipilih')
                expect(checkboxes).to_have_count(4)
                page.unroute('**/api/datasets', fail_delete)

                # Penghapusan sungguhan hanya menyasar kedua ID yang dipilih.
                confirmations = []
                def confirm(dialog):
                    confirmations.append(dialog.message)
                    dialog.accept()

                page.once('dialog', confirm)
                with page.expect_response(lambda response:
                        response.url == url + '/api/datasets'
                        and response.request.method == 'DELETE') as deleted:
                    delete_button.click()
                assert deleted.value.status == 200
                assert set(deletes[-1]['ids']) == {fixtures.target, second_target}
                assert '2 dataset terpilih' in confirmations[0]
                assert 'delete-me.csv' in confirmations[0] and 'delete-second.csv' in confirmations[0]
                assert 'keep-me.csv' not in confirmations[0]
                expect(checkboxes).to_have_count(2)
                expect(selected_count).to_have_text('0 dataset dipilih')
                expect(delete_button).to_be_disabled()
                snapshot = fixtures.snapshot()
                assert {row[0] for row in snapshot['dataset']} == {fixtures.other, unprocessed}
                for table in ('hasil_clustering', 'cluster', 'anggota_cluster', 'hasil_optimasi', 'zona_kurir'):
                    assert len(snapshot[table]) == 1, table
                expect(page.locator('#select-process-dashboard option')).to_have_count(2)

                # Checkbox dan tombol tetap bisa digunakan pada layar ponsel.
                page.set_viewport_size({'width': 390, 'height': 844})
                page.get_by_role('checkbox', name='Pilih dataset keep-me.csv', exact=True).check()
                expect(delete_button).to_be_enabled()
                page.get_by_role('checkbox', name='Pilih dataset keep-me.csv', exact=True).uncheck()
                expect(delete_button).to_be_disabled()

                # Tombol hapus satuan tetap berfungsi; unggahan yang belum diproses tetap tampil.
                page.set_viewport_size({'width': 1365, 'height': 900})
                page.once('dialog', lambda dialog: dialog.accept())
                page.get_by_role('button', name='Hapus dataset keep-me.csv', exact=True).click()
                expect(checkboxes).to_have_count(1)
                expect(page.get_by_role('checkbox', name='Pilih dataset unprocessed.csv', exact=True)).to_be_visible()
                expect(options).to_have_count(1)
                expect(options).to_have_attribute('value', f'db_{unprocessed}')
                assert {row[0] for row in fixtures.snapshot()['dataset']} == {unprocessed}

                # Hapus juga unggahan yang sedang dipilih di dashboard hingga kedua daftar kosong.
                select_all.check()
                page.once('dialog', lambda dialog: dialog.accept())
                delete_button.click()
                expect(page.locator('#delete-dataset-status')).to_have_text('Belum ada dataset tersimpan.')
                expect(select_all).to_be_disabled()
                expect(delete_button).to_be_disabled()
                expect(page.locator('#select-process-dashboard')).to_have_value('none')
                snapshot = fixtures.snapshot()
                assert all(not rows for rows in snapshot.values()), snapshot
                assert not errors, errors
                print('PASS: pilihan individual/semua, pencarian, batal, gagal/coba ulang, '
                      'hapus massal atomik, dataset lain, ponsel, hapus satuan, '
                      'hapus unggahan belum diproses, sinkronisasi Pilih Hasil Proses, dan keadaan kosong.')
            finally:
                browser.close()
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(timeout=5)
        DatasetDeleteTest.tearDownClass()


if __name__ == '__main__':
    main()
