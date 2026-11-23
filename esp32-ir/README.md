# ❄️ Kawalan Aircond (bukan pintar) melalui ESP32 + IR

> Untuk aircond Samsung SmartThings, guna projek utama di folder atas (`../README.md`). Folder ini untuk aircond biasa tanpa WiFi.

Kawal aircond anda dari telefon atau komputer **guna browser sahaja**, tanpa remote
dan tanpa app. Sebuah board kecil ESP32 atau ESP8266 dengan LED inframerah (IR) menyamar
sebagai remote aircond, dan board itu sendiri hos website kawalannya.

```
 Telefon / PC  ──WiFi──►  ESP32 (website + API)  ──isyarat IR──►  Aircond
 http://aircond.local
```

**Ciri-ciri:** hidup/mati, suhu 16–30 °C, mod (Sejuk / Kering / Kipas / Auto / Panas),
kelajuan kipas, swing, turbo, eco, pemasa tutup automatik, login kata laluan, dan sokongan
untuk lebih 70 jenama aircond (Daikin, Panasonic, Midea, Gree, Samsung, LG, Sharp, Mitsubishi,
Haier, TCL, Toshiba, Hitachi, Carrier dan lain-lain) melalui library
[IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266).

---

## 1. Barang yang diperlukan (lebih kurang RM30)

| Barang | Nota |
|---|---|
| ESP32 DevKit **atau** NodeMCU / Wemos D1 mini (ESP8266) | Mana-mana satu |
| LED IR 940 nm (5 mm) | 1–2 biji, boleh selari untuk jarak lebih jauh |
| Transistor NPN 2N2222 / S8050 | Supaya LED cukup terang |
| Perintang 1 kΩ dan 47–100 Ω | |
| Kabel USB + charger telefon 5V | Untuk bekalan kuasa tetap |

## 2. Sambungan litar

```
GPIO4 ──[1kΩ]──► Base (B)  transistor NPN
                 Emitter (E) ──► GND
3V3/5V ──[68Ω]──► Anod LED IR (+, kaki panjang)
                  Katod LED IR (−) ──► Collector (C)
```

* ESP32: GPIO4. NodeMCU/Wemos: pin **D2** (iaitu GPIO4).
* Letak LED **menghala ke aircond**, nampak terus (macam remote biasa).

## 3. Tetapan

Edit `src/config.h`:

```cpp
#define WIFI_SSID     "NamaWiFiAnda"
#define WIFI_PASSWORD "KataLaluanWiFi"
#define WEB_USER      "admin"
#define WEB_PASSWORD  "tukar-saya"   // WAJIB tukar
#define DEFAULT_BRAND "DAIKIN"       // jenama aircond anda
```

## 4. Upload ke board

1. Pasang [VS Code](https://code.visualstudio.com/) + extension **PlatformIO IDE**.
2. Buka folder projek ini.
3. Sambung board dengan USB, kemudian:
   * ESP32: `pio run -e esp32 -t upload`
   * ESP8266: `pio run -e esp8266 -t upload`
4. Buka Serial Monitor (`pio device monitor`) untuk melihat alamat IP.

## 5. Guna

Buka **http://aircond.local** (atau alamat IP yang dipaparkan, cth `http://192.168.1.50`)
di telefon. Log masuk dengan `WEB_USER` / `WEB_PASSWORD`.

> 💡 Di telefon, pilih "Add to Home Screen" supaya ia nampak macam app.

**Jika aircond tak respons:** buka ⚙️ *Tetapan jenama aircond* di bawah halaman, pilih
jenama lain atau tukar model (1, 2, 3…), tekan *Simpan & uji*. Panduan ringkas:

| Jenama aircond | Cuba protokol |
|---|---|
| Daikin | `DAIKIN`, `DAIKIN2`, `DAIKIN176` |
| Panasonic | `PANASONIC_AC` (model 1–6) |
| Midea, Acson, York, Toshiba (sesetengah) | `MIDEA`, `COOLIX` |
| Gree, Cooltek | `GREE` |
| Samsung | `SAMSUNG_AC` |
| Sharp | `SHARP_AC` |
| LG | `LG`, `LG2` |
| Mitsubishi | `MITSUBISHI_AC`, `MITSUBISHI_HEAVY_152` |

Masih tak jumpa? Pasang penerima IR (VS1838B) dan jalankan contoh `IRrecvDumpV2` daripada
library IRremoteESP8266, kemudian tekan butang remote asal: ia akan beritahu nama protokol.

## 6. Cuba website tanpa board (simulasi)

```bash
python3 tools/mock_server.py
# buka http://localhost:8080
```

## API (untuk integrasi, cth Home Assistant / Siri Shortcuts)

| Kaedah | Laluan | Keterangan |
|---|---|---|
| `GET` | `/api/state` | Keadaan semasa |
| `POST` | `/api/state` | Ubah tetapan; semua medan pilihan |
| `GET` | `/api/brands` | Senarai jenama yang disokong |

```bash
curl -u admin:tukar-saya -X POST http://aircond.local/api/state \
     -H 'Content-Type: application/json' \
     -d '{"power":true,"mode":"cool","temp":24,"fan":"auto","timer":120}'
```

Medan: `power` (bool), `mode` (`cool|dry|fan|auto|heat`), `temp` (16–30),
`fan` (`auto|low|medium|high`), `swing`, `turbo`, `econo` (bool), `timer` (minit, 0 = batal),
`brand`, `model`, `send` (`false` = simpan tanpa hantar IR).

## Had & nota

* IR hanya satu hala: jika anda guna remote asal, website tidak tahu perubahan itu.
  Tekan mana-mana butang di website untuk "selaraskan" semula.
* Website hanya boleh dibuka dalam WiFi rumah yang sama. Untuk kawal dari luar rumah,
  guna VPN seperti [Tailscale](https://tailscale.com/) atau WireGuard pada router;
  **jangan** buka port terus ke internet.
* Pemasa tutup akan hilang jika board restart (tetapan lain kekal).

## Struktur projek

```
platformio.ini        Konfigurasi bina (ESP32 & ESP8266)
src/config.h          Tetapan WiFi, login, pin, jenama
src/main.cpp          Firmware: pelayan web + hantar IR
web/index.html        Antara muka website (dibenam automatik ke firmware)
tools/embed_html.py   Skrip pra-bina: index.html -> src/web_ui.h
tools/mock_server.py  Simulasi untuk cuba website di komputer
```
