import unittest

from app import app


class PublicFilesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_public_assets_are_available(self):
        for path in (
            '/css/style.css', '/assets/logo.png', '/js/app.js',
            '/js/data.js', '/js/map.js', '/js/clustering.js',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_internal_files_are_not_served(self):
        for path in (
            '/app.py', '/migrate.py', '/requirements.txt', '/.env',
            '/.env.example', '/.git/config', '/geokurir_db.sql',
            '/database/01_schema.sql', '/database/02_seed.sql',
            '/config/config.py', '/docker-compose.yml', '/Dockerfile',
            '/backups/database.sql', '/templates/index.html',
            '/css/../app.py', '/js/%2e%2e/app.py',
            '/assets/%2e%2e%2fgeokurir_db.sql',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_page_routes_still_work(self):
        for path in ('/', '/index.html', '/dashboard', '/upload', '/zona', '/evaluasi', '/hapus-dataset', '/hapus-dataset.html'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == '__main__':
    unittest.main()
