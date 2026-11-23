# ❄️ Kawalan Aircond Samsung melalui Website

Kawal aircond Samsung anda (yang disambung ke app **SmartThings**) dari mana-mana browser,
seperti telefon, tablet atau komputer, tanpa perlu buka app SmartThings.
**Tiada hardware tambahan diperlukan.**

```
 Browser ──►  server.py (website anda)  ──SmartThings API──►  Awan Samsung  ──►  Aircond
```

**Ciri-ciri**
- Hidup/mati dan tetapkan suhu
- Mod (Sejuk, Kering, Kipas, Auto, Panas, AI…) dan kelajuan kipas
- Mod khas Samsung (WindFree, Tidur, Senyap, Laju…) dan ayunan
- **Suhu dan kelembapan bilik sebenar** daripada sensor aircond
- Pemasa tutup automatik
- Login kata laluan, dan sokongan beberapa aircond (pilih dari website)
- Senarai mod dibina automatik ikut apa yang model aircond anda sokong
- Python sahaja, **tiada `pip install`**

---

## 1. Cuba dulu (simulasi, tanpa akaun Samsung)

```bash
python3 server.py --demo      # Windows: python server.py --demo
# buka http://localhost:8080
```

## 2. Sambung ke aircond sebenar

Perlu Python 3.8 atau lebih baharu. Salin fail tetapan dahulu:

```bash
cp .env.example .env
```

Kemudian pilih **satu** daripada dua cara di bawah.

### Pilihan A: Token peribadi (PAT), untuk cubaan cepat (5 minit)

> ⚠️ Sejak 30 Disember 2024, token peribadi baharu SmartThings **hanya sah 24 jam**.
> Sesuai untuk mencuba sahaja. Untuk guna harian, pakai Pilihan B.

1. Buka https://account.smartthings.com/tokens dan log masuk akaun Samsung.
2. *Generate new token*, kemudian tanda **Devices**: *List all devices*, *See all devices*, *Control all devices*.
3. Salin token itu ke `.env`: `SMARTTHINGS_TOKEN=xxxxxxxx-xxxx-...`
4. Jalankan `python3 server.py` dan buka http://localhost:8080.

### Pilihan B: OAuth, untuk guna jangka panjang (sekali sahaja, ~15 minit)

Dengan cara ini server akan memperbaharui token secara automatik.

1. Pasang [Node.js](https://nodejs.org/), kemudian pasang SmartThings CLI:
   ```bash
   npm install -g @smartthings/cli
   smartthings apps:create
   ```
   (CLI akan minta anda log masuk akaun Samsung dalam browser.)
2. Jawab soalan CLI:
   - Jenis app: **OAuth-In App**
   - Nama: cth `Aircond Web`. Huraian dan ikon boleh dilangkau.
   - Skop: pilih **`r:devices:*`** dan **`x:devices:*`**
   - Redirect URI: **`https://httpbin.org/get`**
3. CLI akan paparkan **OAuth Client Id** dan **OAuth Client Secret**. Salin kedua-duanya
   ke `.env` (`SMARTTHINGS_CLIENT_ID` dan `SMARTTHINGS_CLIENT_SECRET`). Rahsia ini hanya
   dipaparkan sekali.
4. Jalankan `python3 server.py`, buka website, dan tekan **Log masuk Samsung**.
5. Selepas benarkan akses, anda akan sampai ke halaman `httpbin.org` yang ada `?code=...`
   di alamatnya. Salin **keseluruhan alamat** itu, tampal dalam website, dan tekan **Sambung**.

Siap. Token disimpan dalam `data.json` dan diperbaharui sendiri selagi server berjalan.
Jika server dimatikan terlalu lama (lebih kurang sebulan), ulang langkah 4–5.

> 💡 Jika website anda ada domain HTTPS sendiri, set Redirect URI kepada
> `https://domain-anda/auth/callback` (dalam CLI dan `.env`) supaya tak perlu salin-tampal.

## 3. Biar server sentiasa hidup

Server perlu berjalan pada komputer yang sentiasa hidup, cth **Raspberry Pi**, PC lama,
TV box Android (Termux) atau VPS murah. Contoh servis `systemd` untuk Raspberry Pi / Linux:

```ini
# /etc/systemd/system/aircond.service
[Unit]
Description=Kawalan Aircond Web
After=network-online.target

[Service]
WorkingDirectory=/home/pi/claude_code
ExecStart=/usr/bin/python3 server.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now aircond
```

## 4. Kawal dari luar rumah

- **Paling selamat:** [Tailscale](https://tailscale.com/) (percuma). Pasang di server dan telefon,
  kemudian buka `http://<nama-server>:8080` dari mana-mana.
- **Alamat awam HTTPS:** [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  (`cloudflared tunnel --url http://localhost:8080`). **Wajib** tetapkan `WEB_PASSWORD` yang kuat.
- Jangan buka port router terus ke internet tanpa HTTPS.

## API (untuk Siri Shortcuts, Home Assistant, dll.)

| Kaedah | Laluan | Keterangan |
|---|---|---|
| `GET` | `/api/state` | Keadaan semasa, termasuk suhu bilik |
| `POST` | `/api/state` | Ubah tetapan (semua medan pilihan) |
| `GET` | `/api/devices` | Senarai aircond dalam akaun |
| `POST` | `/api/device` | Pilih aircond: `{"id":"..."}` |

```bash
curl -u admin:katalaluan -X POST http://localhost:8080/api/state \
     -H 'Content-Type: application/json' \
     -d '{"power":true,"mode":"cool","temp":24,"fan":"auto","timer":120}'
```

Medan: `power` (bool), `mode` (cth `cool|dry|wind|auto|heat`), `temp`, `fan`
(`auto|low|medium|high|turbo`), `swing` (`fixed|all|vertical|horizontal`), `option`
(`off|windFree|sleep|quiet|speed`…), `timer` (minit, `0` = batal).
Nilai yang diterima bergantung pada model, dan senarainya ada dalam `modes`, `fans`,
`swings` dan `options` dalam respons `GET /api/state`.

## Masalah biasa

| Masalah | Penyelesaian |
|---|---|
| "Token SmartThings tamat tempoh" | PAT sudah lebih 24 jam. Jana baharu, atau tukar ke OAuth |
| "Tiada aircond dijumpai" | Pastikan aircond muncul dalam app SmartThings dengan akaun yang sama |
| Butang ditekan tapi aircond tak berubah | Semak aircond "online" dalam app SmartThings (WiFi aircond) |
| `invalid_grant` semasa log masuk | Kod hanya boleh guna sekali dan cepat tamat. Ulang log masuk |

## Struktur projek

```
server.py        Server web + sambungan SmartThings API (Python, tiada pustaka luar)
web/index.html   Antara muka website (mesra telefon, mod gelap automatik)
.env.example     Contoh tetapan, salin ke .env
esp32-ir/        Alternatif: kawal aircond BUKAN pintar guna ESP32 + LED IR
```

`.env` dan `data.json` mengandungi rahsia. Kedua-duanya sudah dalam `.gitignore`,
jadi jangan commit.
