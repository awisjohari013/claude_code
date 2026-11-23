#pragma once
// =====================================================================
//  TETAPAN - ubah bahagian ini sebelum upload ke board
// =====================================================================

// WiFi rumah anda
#define WIFI_SSID     "NamaWiFiAnda"
#define WIFI_PASSWORD "KataLaluanWiFi"

// Login untuk website (elak orang lain dalam WiFi yang sama kacau aircond).
// Biarkan WEB_USER kosong "" untuk matikan login.
#define WEB_USER      "admin"
#define WEB_PASSWORD  "tukar-saya"

// Nama peranti: buka http://aircond.local dalam browser
#define HOSTNAME      "aircond"

// Pin GPIO yang disambung ke LED IR (melalui transistor).
// ESP32: GPIO4  |  NodeMCU/Wemos: GPIO4 = pin "D2"
#define IR_LED_PIN    4

// Jenama aircond lalai (boleh ditukar kemudian dari website).
// Contoh: "DAIKIN", "PANASONIC_AC", "MIDEA", "GREE", "SAMSUNG_AC",
//         "LG", "SHARP_AC", "MITSUBISHI_AC", "HAIER_AC", "TCL112AC",
//         "TOSHIBA_AC", "HITACHI_AC", "CARRIER_AC64", "COOLIX"
#define DEFAULT_BRAND "DAIKIN"
