<div align="center">

# OpenNDS — Flask Captive Portal FAS

**WiFi Hotspot Captive Portal berbasis AI**
dibangun di atas **openNDS FAS**, **Flask**, dan **Groq API**

[![Preview Demo](https://img.shields.io/badge/Live_Demo-Preview_Interaktif-d97757?style=for-the-badge)](https://Kendo-id.github.io/Opennds-auth-AI-challenge/preview.html)
[![OpenWrt](https://img.shields.io/badge/OpenWrt-GL--B1300-00b4d8?style=flat-square&logo=openwrt)](https://openwrt.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-black?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---
![Arsitektur](https://kendo-id.github.io/Opennds-auth-AI-challenge/architecture.svg)



[DEMO Preview](https://kendo-id.github.io/Opennds-auth-AI-challenge/preview.html)
---

   

## 📖 Deskripsi / Description

**Bahasa Indonesia:**  
Jangkrik adalah sistem captive portal untuk jaringan WiFi yang mengintegrasikan OpenNDS (pada router GL-iNet/OpenWrt) dengan backend Flask. Pengguna yang terhubung ke WiFi akan diarahkan ke halaman portal, di mana mereka harus menjawab kuis sederhana untuk mendapatkan akses internet. Selama menunggu, pengguna dapat berinteraksi dengan asisten AI bernama **Kendo** — karakter yang blak-blakan, ketus, dan latah — yang ditenagai oleh Groq LLM.

**English:**  
Jangkrik is a WiFi captive portal system integrating OpenNDS (on GL-iNet/OpenWrt routers) with a Flask backend. Users connecting to the WiFi are redirected to a portal page where they must answer a simple quiz to gain internet access. While waiting, users can chat with an AI assistant named **Kendo** — a blunt, grumpy, and easily startled character — powered by the Groq LLM API.

---

## ✨ Fitur / Features

| Fitur | Deskripsi | Description |
|---|---|---|
| 🔒 Quiz Auth | Autentikasi via kuis sebelum akses internet | Quiz-based authentication before internet access |
| 🤖 AI Chat | Asisten AI karakter Kendo (Groq LLM) | Kendo AI assistant character (Groq LLM) |
| 🌐 Bilingual UI | Antarmuka Bahasa Indonesia | Indonesian language interface |
| 📱 Responsive | Tampilan mobile-friendly | Mobile-friendly layout |
| 🔐 HTTPS | Sertifikat self-signed + redirect HTTP→HTTPS | Self-signed cert + HTTP→HTTPS redirect |
| 🔄 FAS Integration | Integrasi penuh dengan openNDS FAS | Full openNDS FAS integration |
| 📋 About Modal | Bottom-sheet info portal | Bottom-sheet info modal |
| 🌍 Kamus Daerah | Fitur kamus bahasa daerah | Regional language dictionary feature |

---

## 🏗️ Arsitektur Sistem / System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      JARINGAN WIFI                          │
│                                                             │
│  [User Device]──WiFi──▶[GL-iNet Router]                    │
│       │                 OpenWrt + openNDS                   │
│       │                 client_params.sh (FAS)              │
│       │                        │                            │
│       │              FAS redirect (HTTP)                    │
│       │                        ▼                            │
│       └──────────────▶[Flask Backend]──▶[Groq API]         │
│                        Python + HTTPS     LLM (llama3)      │
│                        Quiz + AI Chat     Kendo character   │
│                        (Nginx optional)                     │
└─────────────────────────────────────────────────────────────┘
```

### Komponen Utama / Main Components

**1. GL-iNet Router (OpenWrt)**
- Menjalankan openNDS sebagai captive portal engine
- Meng-generate HTML portal page dan redirect ke Flask
- Mengelola token akses internet per client

**2. Flask Backend (`app.py`)**
- Menerima redirect dari openNDS via FAS
- Menyajikan halaman portal (quiz + AI chat)
- Memvalidasi jawaban kuis dan meminta token ke openNDS
- Meneruskan pertanyaan user ke Groq API
- Berjalan di HTTPS dengan sertifikat self-signed

**3. Groq API**
- Menyediakan LLM (model llama3) untuk AI chat
- Karakter Kendo: blak-blakan, ketus, latah
- System prompt dalam Bahasa Indonesia

**4. Nginx (Opsional)**
- Reverse proxy di depan Flask
- Menangani HTTPS termination
- HTTP → HTTPS redirect (dengan pengecualian `/portal` untuk openNDS)

---

## 🔄 Cara Kerja / How It Works

### Alur Autentikasi / Authentication Flow

```
1. User connect ke WiFi "Jangkrik AI"
        │
        ▼
2. openNDS deteksi client baru
   → redirect browser ke Flask portal
        │
        ▼
3. User membuka halaman portal
   → tampil kuis + chat Kendo Assistant
        │
        ▼
4. User jawab kuis dengan benar
   → Flask kirim token request ke openNDS
   → openNDS grant akses internet
        │
        ▼
5. User dapat akses internet ✓
```

### Alur AI Chat / AI Chat Flow

```
User ketik pertanyaan di portal
        │
        ▼
Flask terima request (/chat endpoint)
        │
        ▼
Flask kirim ke Groq API
        │
        ▼
Groq kembalikan respons LLM
        │
        ▼
Flask forward ke browser user
```

---

## 📁 Struktur Project / Project Structure

```
jangkrik-ai/
│
├── app.py                    # Flask main application
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (API keys)
│
├── templates/
│   ├── portal.html           # Halaman portal utama (quiz + chat)
│   └── blocked.html          # Halaman jika akses ditolak
│
├── static/
│   ├── css/
│   │   └── style.css         # Stylesheet portal
│   └── js/
│       └── portal.js         # AudioContext unlock + UI logic
│
├── certs/
│   ├── cert.pem              # Self-signed certificate
│   └── key.pem               # Private key
│
├── opennds/
│   ├── client_params.sh      # FAS script (dijalankan di router)
│   └── opennds.conf          # Konfigurasi openNDS
│
├── nginx/
│   └── jangkrik.conf         # Nginx reverse proxy config (opsional)
│
└── README.md
```

---

## 🛠️ Instalasi / Installation

### Prasyarat / Prerequisites

- Router GL-iNet dengan OpenWrt (diuji di GL-B1300, OpenWrt 21.02.2)
- openNDS terinstall di router
- Flask Bakend kali chroot di router Gl.inet GL-B1300
- ** flask bakend bisa menggunakan PC/lokal, STB, Termux Android, atau router itu sendiri dgn tambahan extroot**
- Akun Groq API (gratis di [console.groq.com](https://console.groq.com))

---

### 1. Clone Repository

```bash
git clone git@github.com:Kendo-id/Opennds-auth-AI-challenge.git
cd Opennds-auth-AI-challenge
```

---

### 2. Setup Flask Backend

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Buat file `.env`:**
```bash
cp .env.example .env
nano .env
```

Isi dengan:
```env
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=random_secret_key
# Gateway address openNDS
GATEWAY_ADDRESS=192.168.8.1
# openNDS FAS Key (harus sama dengan faskey di config opennds)
FAS_KEY=1234567890 

```

**Generate sertifikat self-signed:**
```bash
mkdir certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem \
  -out certs/cert.pem -days 365 -nodes \
  -subj "/CN=jangkrik.local"
```

**Jalankan Flask:**
```bash
python app.py
```

Flask berjalan di `https://0.0.0.0:5000`

---

### 3. Konfigurasi openNDS di Router

SSH ke router:
```bash
ssh root@192.168.8.1
```

Edit konfigurasi openNDS:
```bash
nano /etc/config/opennds
```

Tambahkan/sesuaikan:
```
config opennds
    option fас_enable '1'
    option fas_port '5000'
    option fas_secure_enabled '1'
    option fas_remoteip '192.168.8.100'   # IP server Flask
    option fas_remotefqdn 'jangkrik.local'
    option faskey 'your_shared_secret'
```

Upload script FAS ke router:
```bash
scp opennds/client_params.sh root@192.168.8.1:/usr/lib/opennds/
chmod +x /usr/lib/opennds/client_params.sh
```

Restart openNDS:
```bash
service opennds restart
```

---

### 4. (Opsional) Setup Nginx Reverse Proxy

Install Nginx:
```bash
sudo apt install nginx
```

Copy konfigurasi:
```bash
sudo cp nginx/jangkrik.conf /etc/nginx/sites-available/jangkrik
sudo ln -s /etc/nginx/sites-available/jangkrik /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Isi `nginx/jangkrik.conf`:
```nginx
server {
    listen 80;
    server_name _;

    # Pengecualian untuk openNDS FAS — jangan redirect ke HTTPS
    location /portal {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Redirect semua traffic lain ke HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /path/to/certs/cert.pem;
    ssl_certificate_key /path/to/certs/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---


## ⚙️ Konfigurasi Karakter Kendo / Kendo Character Config

Karakter AI Kendo Assistant dikonfigurasi via system prompt di `app.py`:

```python
SYSTEM_PROMPT = """Nama Kamu adalah Kendo, asisten AI di portal WiFi Jangkrik AI.
Gaya Bicara: blak-blakan, ketus, jutek, Cuek dan latah 😂.
Meski ketus, kamu tetap membantu dan menjawab pertanyaan dengan benar.
Jawab dalam Bahasa Indonesia."""
```

Kamu bisa mengubah karakter sesuai kebutuhan dengan mengedit `SYSTEM_PROMPT` di `app.py`.

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---|---|
| Portal tidak muncul saat connect WiFi | Cek `service opennds status` di router, pastikan FAS enabled |
| Error "Internal Server Error" di Flask | Cek non-ASCII character di system prompt — hapus emoji/karakter khusus |
| Mikrofon tidak bisa diakses | Pastikan site diakses via HTTPS, bukan HTTP |
| AI tidak merespons | Cek `GROQ_API_KEY` di `.env`, cek koneksi internet server |
| `client_params.sh` output kosong | Jangan pakai heredoc; gunakan variabel + `echo "$var"` |
| HTTPS cert error di browser | Normal untuk self-signed cert — klik "Advanced → Proceed" |

---

## 📦 Dependencies

```
flask
flask-cors
groq
python-dotenv
pyopenssl
requests
```

Install semua dengan:
```bash
pip install -r requirements.txt
```

---

## 🤝 Kontribusi / Contributing

Pull request dan issue sangat disambut! / Pull requests and issues are very welcome!

1. Fork repository ini
2. Buat branch baru: `git checkout -b fitur-baru`
3. Commit perubahan: `git commit -m "tambah fitur baru"`
4. Push ke branch: `git push origin fitur-baru`
5. Buka Pull Request

---

## 📄 Lisensi / License

MIT License — bebas digunakan dan dimodifikasi. / MIT License — free to use and modify.

🚫 Dilarang untuk diperjualbelikan !!
---

## 👤 Author

**Kendo-id (a.k.a si_GILA)**  
GitHub: [@Kendo-id](https://github.com/Kendo-id)
---
