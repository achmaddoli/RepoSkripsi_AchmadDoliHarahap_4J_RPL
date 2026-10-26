# 🚀 Panduan Menjalankan Sistem GeoKurir Malang (Laptop Baru & VPS)

Panduan praktis langkah demi langkah untuk menjalankan aplikasi **GeoKurir Malang** pada laptop baru (Windows/macOS/Linux) maupun server VPS (Ubuntu/Debian).

---

## 📌 Daftar Isi
1. [Prasyarat Sistem](#1-prasyarat-sistem)
2. [Langkah 1: Setup di Laptop Baru (Localhost)](#2-langkah-setup-di-laptop-baru-localhost)
3. [Langkah 2: Setup di Server VPS (Ubuntu / Debian)](#3-langkah-setup-di-server-vps-ubuntu--debian)
4. [Langkah 3 (Opsional VPS): Nginx Reverse Proxy & Domain SSL](#4-langkah-opsional-vps-nginx-reverse-proxy--domain-ssl)
5. [Cheatsheet Perintah Docker Compose](#5-cheatsheet-perintah-docker-compose)
6. [Backup & Restore Database](#6-backup--restore-database)
7. [Solusi Kendala Umum (Troubleshooting)](#7-solusi-kendala-umum-troubleshooting)

---

## 1. Prasyarat Sistem

Pastikan laptop atau VPS sudah terpasang:
* **Git**
* **Docker Engine & Docker Compose**
  * *Windows / macOS:* Pasang [Docker Desktop](https://www.docker.com/products/docker-desktop/) (pastikan Docker Desktop sudah running).
  * *Linux / VPS:* Pasang Docker via terminal:
    ```bash
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    # Logout dan login kembali agar izin grup docker aktif
    ```

---

## 2. Langkah Setup di Laptop Baru (Localhost)

Cukup **3 langkah praktis**:

### 1. Masuk ke Direktori Proyek
```bash
git clone <URL_REPOSITORY_ANDA> websitegeokurir
cd websitegeokurir
```

### 2. Buat File Konfigurasi `.env`
Salin template konfigurasi yang sudah disediakan:
```bash
cp .env.example .env
```
*(Opsional)* Buka file `.env` menggunakan teks editor (VS Code, Notepad, atau nano). Masukkan `GOOGLE_MAPS_API_KEY` jika Anda memiliki API key resmi Google Maps.

### 3. Jalankan Docker Compose
```bash
docker compose up -d --build
```
> **Catatan:** Flag `--build` memastikan image Python Flask dirakit secara otomatis untuk pertama kali.

Pada perangkat atau server baru dengan volume baru, database dimulai kosong.
Docker hanya membuat struktur tabel dari `database/01_schema.sql`; dump
`geokurir_db.sql` dan data contoh tidak diimpor. Upload dataset melalui website
untuk mulai menggunakan aplikasi. Restart atau deploy ulang dengan volume yang
sama mempertahankan data. Saat pindah perangkat dan ingin mulai kosong, cukup
salin kode, buat `.env` baru, dan jangan pindahkan volume PostgreSQL/restore backup.

### 4. Akses Aplikasi
* **Website GeoKurir Malang:** Buka browser di 👉 **[http://localhost:5000](http://localhost:5000)**
* **Database GUI (Adminer):** Buka browser di 👉 **[http://localhost:8080](http://localhost:8080)**  
  *(Sistem: `PostgreSQL`, Server: `postgres`, User: `geokurir`, Password: `geokurir_secret`, Database: `geokurir_db`)*

---

## 3. Langkah Setup di Server VPS (Ubuntu / Debian)

Jika Anda ingin menjalankan aplikasi di cloud VPS (misal: DigitalOcean, Linode, AWS EC2, GCP Compute Engine, Biznet, DomaiNesia):

### 1. Update Server & Install Docker
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ufw

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker
```

### 2. Atur Firewall Server (UFW)
Buka port SSH, HTTP, HTTPS, dan port aplikasi jika diakses langsung:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5000/tcp
sudo ufw enable
```

### 3. Clone Proyek & Siapkan `.env`
```bash
git clone <URL_REPOSITORY_ANDA> websitegeokurir
cd websitegeokurir
cp .env.example .env
nano .env  # Sesuaikan konfigurasi jika diperlukan (Ctrl+O Enter, Ctrl+X untuk keluar)
```

### 4. Jalankan Aplikasi di Background
```bash
docker compose up -d --build
```

### 5. Akses Aplikasi VPS
Buka di browser menggunakan IP Publik VPS Anda:
* Website: `http://<IP_PUBLIK_VPS>:5000`
* PostgreSQL dan Adminer hanya terbuka pada localhost server. Untuk membuka
  Adminer dari laptop, gunakan SSH tunnel:
  `ssh -L 18080:127.0.0.1:8080 user@<IP_PUBLIK_VPS>`, lalu buka
  `http://localhost:18080` di laptop.

---

## 4. Langkah (Opsional VPS): Nginx Reverse Proxy & Domain SSL

Jika Anda memiliki domain (contoh: `geokurir.domainanda.com`) dan ingin menggunakan HTTPS (port 80 & 443 standar tanpa `:5000`):

1. **Install Nginx & Certbot:**
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```

2. **Buat File Konfigurasi Nginx:**
   ```bash
   sudo nano /etc/nginx/sites-available/geokurir
   ```
   Isi dengan konfigurasi berikut:
   ```nginx
   server {
       server_name geokurir.domainanda.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **Aktifkan Konfigurasi & Reload Nginx:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/geokurir /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **Pasang SSL Gratis (Let's Encrypt HTTPS):**
   ```bash
   sudo certbot --nginx -d geokurir.domainanda.com
   ```
   Sekarang website Anda dapat diakses aman di `https://geokurir.domainanda.com`.

---

## 5. Cheatsheet Perintah Docker Compose

Gunakan perintah ini di dalam folder `websitegeokurir/`:

| Tujuan | Perintah |
| :--- | :--- |
| **Menjalankan aplikasi di background** | `docker compose up -d` |
| **Rebuild setelah ada perubahan kode** | `docker compose up -d --build` |
| **Melihat status kontainer aktif** | `docker compose ps` |
| **Melihat log backend Flask secara realtime** | `docker compose logs -f web` |
| **Melihat log PostgreSQL** | `docker compose logs -f postgres` |
| **Merestart seluruh sistem** | `docker compose restart` |
| **Merestart hanya web Flask** | `docker compose restart web` |
| **Menghentikan aplikasi tanpa hapus data** | `docker compose down` |
| **Menghentikan aplikasi & hapus data DB (reset)** | `docker compose down -v` |

---

## 6. Backup & Restore Database

### Cara Backup Database PostgreSQL:
```bash
docker exec -t geokurir-postgres pg_dump -U geokurir geokurir_db > backup_geokurir_$(date +%Y%m%d).sql
```

### Cara Restore Database dari File Backup:
```bash
cat backup_geokurir_20261022.sql | docker exec -i geokurir-postgres psql -U geokurir -d geokurir_db
```

---

## 7. Solusi Kendala Umum (Troubleshooting)

### Q: Error `unknown shorthand flag: 'd' in -d`
* **Penyebab:** Mengetik `docker-compose -d up`.
* **Solusi:** Ketik `docker compose up -d` (flag `-d` diletakkan setelah `up`).

### Q: Port 5000 atau 5432 sudah terpakai oleh aplikasi lain
* **Penyebab:** Di laptop/VPS sudah ada PostgreSQL lokal atau aplikasi lain di port 5000.
* **Solusi:** Edit file `.env`, ubah port yang bentrok (misal `FLASK_PORT=5001` atau `DB_PORT=5433`), lalu jalankan `docker compose up -d`.

### Q: Perubahan file Python tidak langsung ter-update di web
* **Solusi:** Karena mode produksi mematikan debug reload, jalankan perintah:
  ```bash
  docker compose restart web
  ```

### Q: Ingin mereset total database agar kosong kembali
* **Solusi:** Cadangkan dahulu. Perintah berikut menghapus seluruh data volume:
  ```bash
  docker compose down -v
  docker compose up -d
  ```
  *(Database hanya membuat tabel dari `01_schema.sql`, tanpa data awal).
  Restart biasa tidak mengosongkan database.*
