// =====================================================================
//  Kawalan Aircond melalui Website (ESP32 / ESP8266 + LED IR)
//  Board ini menjadi "remote" aircond dan sekali gus hos website kawalan.
// =====================================================================
#include <Arduino.h>
#include <EEPROM.h>
#include <ArduinoJson.h>
#include <IRremoteESP8266.h>
#include <IRac.h>
#include <IRutils.h>

#if defined(ESP32)
  #include <WiFi.h>
  #include <WebServer.h>
  #include <ESPmDNS.h>
  using WebServerT = WebServer;
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266WebServer.h>
  #include <ESP8266mDNS.h>
  using WebServerT = ESP8266WebServer;
#else
  #error "Board tidak disokong. Guna ESP32 atau ESP8266."
#endif

#include "config.h"
#include "web_ui.h"

// ---------------------------------------------------------------------
//  Keadaan aircond (disimpan dalam EEPROM supaya kekal selepas restart)
// ---------------------------------------------------------------------
static const uint32_t STATE_MAGIC = 0xAC0C0002;

struct AcState {
  uint32_t magic;
  char     brand[32];   // nama protokol IRremoteESP8266, cth "DAIKIN"
  int16_t  model;       // model protokol (kebanyakan jenama guna 1)
  bool     power;
  uint8_t  mode;        // 0=auto 1=cool 2=dry 3=fan 4=heat
  uint8_t  temp;        // 16..30 °C
  uint8_t  fan;         // 0=auto 1=low 2=medium 3=high
  bool     swing;
  bool     turbo;
  bool     econo;
};

static const char* const MODE_NAMES[] = {"auto", "cool", "dry", "fan", "heat"};
static const char* const FAN_NAMES[]  = {"auto", "low", "medium", "high"};
static const uint8_t MODE_COUNT = 5, FAN_COUNT = 4;
static const uint8_t TEMP_MIN = 16, TEMP_MAX = 30;

AcState     state;
IRac        ac(IR_LED_PIN);
WebServerT  server(80);
uint32_t    offTimerAt = 0;   // millis() bila aircond akan dimatikan (0 = tiada)

// ---------------------------------------------------------------------
//  Simpan / muat keadaan
// ---------------------------------------------------------------------
void setDefaults() {
  memset(&state, 0, sizeof(state));
  state.magic = STATE_MAGIC;
  strlcpy(state.brand, DEFAULT_BRAND, sizeof(state.brand));
  state.model = 1;
  state.power = false;
  state.mode  = 1;   // cool
  state.temp  = 24;
  state.fan   = 0;   // auto
}

void loadState() {
  EEPROM.begin(sizeof(AcState));
  EEPROM.get(0, state);
  if (state.magic != STATE_MAGIC) setDefaults();
  state.brand[sizeof(state.brand) - 1] = '\0';
  if (state.mode >= MODE_COUNT) state.mode = 1;
  if (state.fan  >= FAN_COUNT)  state.fan  = 0;
  state.temp = constrain(state.temp, TEMP_MIN, TEMP_MAX);
}

void saveState() {
  EEPROM.put(0, state);
  EEPROM.commit();
}

// ---------------------------------------------------------------------
//  Hantar isyarat IR ke aircond
// ---------------------------------------------------------------------
bool sendIr() {
  decode_type_t proto = strToDecodeType(state.brand);
  if (!IRac::isProtocolSupported(proto)) {
    Serial.printf("Jenama '%s' tidak disokong\n", state.brand);
    return false;
  }
  static const stdAc::opmode_t modes[] = {
    stdAc::opmode_t::kAuto, stdAc::opmode_t::kCool, stdAc::opmode_t::kDry,
    stdAc::opmode_t::kFan,  stdAc::opmode_t::kHeat};
  static const stdAc::fanspeed_t fans[] = {
    stdAc::fanspeed_t::kAuto, stdAc::fanspeed_t::kLow,
    stdAc::fanspeed_t::kMedium, stdAc::fanspeed_t::kHigh};

  ac.next.protocol = proto;
  ac.next.model    = state.model;
  ac.next.power    = state.power;
  ac.next.mode     = modes[state.mode];
  ac.next.celsius  = true;
  ac.next.degrees  = state.temp;
  ac.next.fanspeed = fans[state.fan];
  ac.next.swingv   = state.swing ? stdAc::swingv_t::kAuto : stdAc::swingv_t::kOff;
  ac.next.swingh   = stdAc::swingh_t::kOff;
  ac.next.turbo    = state.turbo;
  ac.next.econo    = state.econo;
  ac.next.quiet    = false;
  ac.next.light    = true;
  ac.next.beep     = true;
  ac.next.filter   = false;
  ac.next.clean    = false;
  ac.next.sleep    = -1;
  ac.next.clock    = -1;
  bool ok = ac.sendAc();
  Serial.printf("IR -> %s power=%d mode=%s temp=%d fan=%s : %s\n", state.brand,
                state.power, MODE_NAMES[state.mode], state.temp,
                FAN_NAMES[state.fan], ok ? "OK" : "GAGAL");
  return ok;
}

// ---------------------------------------------------------------------
//  Pembantu web
// ---------------------------------------------------------------------
bool checkAuth() {
  if (strlen(WEB_USER) == 0) return true;
  if (server.authenticate(WEB_USER, WEB_PASSWORD)) return true;
  server.requestAuthentication();
  return false;
}

int indexOf(const char* const* list, uint8_t n, const char* value) {
  for (uint8_t i = 0; i < n; i++)
    if (strcmp(list[i], value) == 0) return i;
  return -1;
}

void sendStateJson(bool irOk = true) {
  JsonDocument doc;
  doc["power"] = state.power;
  doc["mode"]  = MODE_NAMES[state.mode];
  doc["temp"]  = state.temp;
  doc["fan"]   = FAN_NAMES[state.fan];
  doc["swing"] = state.swing;
  doc["turbo"] = state.turbo;
  doc["econo"] = state.econo;
  doc["brand"] = state.brand;
  doc["model"] = state.model;
  doc["timer"] = offTimerAt ? (int)((offTimerAt - millis()) / 60000UL) + 1 : 0;
  doc["irOk"]  = irOk;
  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// ---------------------------------------------------------------------
//  Laluan (routes) web
// ---------------------------------------------------------------------
void handleRoot() {
  if (!checkAuth()) return;
  server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void handleGetState() {
  if (!checkAuth()) return;
  sendStateJson();
}

// POST /api/state  body: {"power":true,"temp":23,...} (semua medan pilihan)
void handlePostState() {
  if (!checkAuth()) return;
  JsonDocument doc;
  if (deserializeJson(doc, server.arg("plain"))) {
    server.send(400, "application/json", "{\"error\":\"JSON tidak sah\"}");
    return;
  }
  if (doc["power"].is<bool>()) state.power = doc["power"];
  if (doc["temp"].is<int>())   state.temp  = constrain(doc["temp"].as<int>(), TEMP_MIN, TEMP_MAX);
  if (doc["swing"].is<bool>()) state.swing = doc["swing"];
  if (doc["turbo"].is<bool>()) state.turbo = doc["turbo"];
  if (doc["econo"].is<bool>()) state.econo = doc["econo"];
  if (doc["model"].is<int>())  state.model = doc["model"].as<int>();
  if (doc["mode"].is<const char*>()) {
    int i = indexOf(MODE_NAMES, MODE_COUNT, doc["mode"]);
    if (i >= 0) state.mode = i;
  }
  if (doc["fan"].is<const char*>()) {
    int i = indexOf(FAN_NAMES, FAN_COUNT, doc["fan"]);
    if (i >= 0) state.fan = i;
  }
  if (doc["brand"].is<const char*>()) {
    const char* b = doc["brand"];
    if (IRac::isProtocolSupported(strToDecodeType(b)))
      strlcpy(state.brand, b, sizeof(state.brand));
  }
  if (doc["timer"].is<int>()) {   // minit sebelum auto-off, 0 = batal
    int m = constrain(doc["timer"].as<int>(), 0, 24 * 60);
    offTimerAt = m ? millis() + (uint32_t)m * 60000UL : 0;
    if (offTimerAt == 0 && m) offTimerAt = 1;
  }
  if (!state.power) offTimerAt = 0;

  bool ok = true;
  if (!doc["send"].is<bool>() || doc["send"].as<bool>()) ok = sendIr();
  saveState();
  sendStateJson(ok);
}

// GET /api/brands -> senarai semua jenama/protokol yang disokong
void handleBrands() {
  if (!checkAuth()) return;
  String out = "[";
  bool first = true;
  for (int i = 1; i <= kLastDecodeType; i++) {
    decode_type_t p = (decode_type_t)i;
    if (!IRac::isProtocolSupported(p)) continue;
    if (!first) out += ',';
    out += '"';
    out += typeToString(p);
    out += '"';
    first = false;
  }
  out += ']';
  server.send(200, "application/json", out);
}

// ---------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n== Kawalan Aircond ==");

  loadState();
  ac.initState(&ac.next);

  WiFi.mode(WIFI_STA);
#if defined(ESP32)
  WiFi.setHostname(HOSTNAME);
#else
  WiFi.hostname(HOSTNAME);
#endif
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Menyambung ke WiFi '%s'", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }
  Serial.printf("\nBerjaya! Buka http://%s  atau  http://%s.local\n",
                WiFi.localIP().toString().c_str(), HOSTNAME);

  if (MDNS.begin(HOSTNAME)) MDNS.addService("http", "tcp", 80);

  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/state", HTTP_GET, handleGetState);
  server.on("/api/state", HTTP_POST, handlePostState);
  server.on("/api/brands", HTTP_GET, handleBrands);
  server.onNotFound([] { server.send(404, "text/plain", "Tidak dijumpai"); });
  server.begin();
}

void loop() {
  server.handleClient();
#if defined(ESP8266)
  MDNS.update();
#endif

  // Pemasa auto-off
  if (offTimerAt && (int32_t)(millis() - offTimerAt) >= 0) {
    offTimerAt = 0;
    state.power = false;
    sendIr();
    saveState();
    Serial.println("Pemasa tamat: aircond dimatikan");
  }

  // Sambung semula jika WiFi terputus
  static uint32_t lastCheck = 0;
  if (millis() - lastCheck > 10000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) WiFi.reconnect();
  }
}
