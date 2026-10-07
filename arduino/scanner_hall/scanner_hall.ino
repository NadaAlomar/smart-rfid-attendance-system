/*
 * ============================================================
 *  سكانر القاعة — NodeMCU ESP8266
 *  MFRC522 RFID Reader + WiFi + API
 * ============================================================
 *
 *  التوصيلات (MFRC522 → NodeMCU):
 *  --------------------------------
 *  SDA  (SS)  → D8  (GPIO15)
 *  SCK        → D5  (GPIO14)
 *  MOSI       → D7  (GPIO13)
 *  MISO       → D6  (GPIO12)
 *  RST        → D1  (GPIO5)
 *  GND        → GND
 *  3.3V       → 3.3V
 *  IRQ        → لا يوصل
 *
 *  LED الأخضر  → D0  (GPIO16)
 *  LED الأحمر  → D3  (GPIO0)
 *  بازر        → D4  (GPIO2)  — اختياري
 *
 *  المكتبات المطلوبة (Library Manager):
 *  - MFRC522 by GithubCommunity
 *  - ArduinoJson by Benoit Blanchon
 * ============================================================
 *
 *  آلية التوكن:
 *  — يبحث أولاً عن التوكن في EEPROM
 *  — اذا لم يجده يطلب التوكن من السيرفر تلقائياً
 *  — يحفظ التوكن في EEPROM للاستخدام القادم
 * ============================================================
 */

#include <SPI.h>
#include <MFRC522.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <WiFiClient.h>
#include <EEPROM.h>

// ══════════════════════════════════════════
//  اعدل هذه القيم فقط
// ══════════════════════════════════════════
//  يجب أن يكون NodeMCU والكمبيوتر على نفس شبكة Wi-Fi
#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"
#define SERVER_IP      "YOUR_SERVER_IP"
#define SERVER_PORT    5000
#define DEVICE_ID      "DEVICE001"
// ══════════════════════════════════════════

#define SS_PIN   15   // D8
#define RST_PIN   5   // D1

#define LED_GREEN  16   // D0
#define LED_RED     0   // D3
#define BUZZER_PIN  2   // D4

#define COOLDOWN_MS    2000
#define WIFI_TIMEOUT   15000
#define HTTP_TIMEOUT   6000

// EEPROM layout for token storage
#define EEPROM_SIZE      64
#define EEPROM_TOKEN_ADDR 0
#define EEPROM_TOKEN_LEN  33   // 32 chars + null terminator
#define EEPROM_MAGIC_ADDR  33
#define EEPROM_MAGIC_VAL   0xA5



MFRC522 rfid(SS_PIN, RST_PIN);

String lastUID = "";
unsigned long lastScanTime = 0;
bool wifiConnected = false;
String deviceToken = "";

// ═══════════════════════════════════════════════════════════
//  EEPROM — حفظ وقراءة التوكن
// ═══════════════════════════════════════════════════════════
void saveTokenToEEPROM(const String& token) {
  EEPROM.begin(EEPROM_SIZE);
  for (int i = 0; i < EEPROM_TOKEN_LEN; i++) {
    if (i < (int)token.length()) {
      EEPROM.write(EEPROM_TOKEN_ADDR + i, token[i]);
    } else {
      EEPROM.write(EEPROM_TOKEN_ADDR + i, 0);
    }
  }
  EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VAL);
  EEPROM.commit();
  EEPROM.end();
  Serial.println("[EEPROM] تم حفظ التوكن");
}

String loadTokenFromEEPROM() {
  EEPROM.begin(EEPROM_SIZE);
  byte magic = EEPROM.read(EEPROM_MAGIC_ADDR);
  if (magic != EEPROM_MAGIC_VAL) {
    EEPROM.end();
    return "";
  }
  char buf[EEPROM_TOKEN_LEN] = {0};
  for (int i = 0; i < EEPROM_TOKEN_LEN - 1; i++) {
    buf[i] = EEPROM.read(EEPROM_TOKEN_ADDR + i);
    if (buf[i] == 0) break;
  }
  EEPROM.end();
  String token = String(buf);
  token.trim();
  return token;
}

// ═══════════════════════════════════════════════════════════
//  جلب التوكن من السيرفر
// ═══════════════════════════════════════════════════════════
String fetchTokenFromServer() {
  WiFiClient client;
  HTTPClient http;

  String url = "http://" + String(SERVER_IP) + ":" +
               String(SERVER_PORT) + "/api/devices";

  http.begin(client, url);
  http.setTimeout(HTTP_TIMEOUT);

  int code = http.GET();
  if (code != 200) {
    Serial.println("[TOKEN] فشل جلب الأجهزة: " + String(code));
    http.end();
    return "";
  }

  String resp = http.getString();
  http.end();

  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, resp);
  if (err) {
    Serial.println("[TOKEN] خطأ JSON");
    return "";
  }

  JsonArray devices = doc["devices"].as<JsonArray>();
  for (JsonObject dev : devices) {
    const char* did = dev["device_id"] | "";
    if (String(did) == String(DEVICE_ID)) {
      const char* token = dev["device_token"] | "";
      Serial.println("[TOKEN] تم العثور على التوكن");
      return String(token);
    }
  }

  Serial.println("[TOKEN] لم يتم العثور على الجهاز في السيرفر");
  return "";
}

// ═══════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  pinMode(LED_GREEN,  OUTPUT);
  pinMode(LED_RED,    OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LED_GREEN,  LOW);
  digitalWrite(LED_RED,    LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.println("\n================================");
  Serial.println("  AUST - سكانر الحضور بالقاعة");
  Serial.println("================================");

  connectWiFi();

#ifdef HARDCODED_TOKEN
  deviceToken = String(HARDCODED_TOKEN);
  saveTokenToEEPROM(deviceToken);
  Serial.println("[TOKEN] تم حفظ التوكن من HARDCODED_TOKEN في EEPROM");
#else
  deviceToken = loadTokenFromEEPROM();
  if (deviceToken.length() > 0) {
    Serial.println("[TOKEN] تم تحميل التوكن من EEPROM");
  } else {
    Serial.println("[TOKEN] لا يوجد توكن محفوظ — جاري الجلب من السيرفر...");
    deviceToken = fetchTokenFromServer();
    if (deviceToken.length() > 0) {
      saveTokenToEEPROM(deviceToken);
      Serial.println("[TOKEN] تم حفظ التوكن: " + deviceToken);
    } else {
      Serial.println("[TOKEN] تحذير: لم يتم العثور على توكن!");
      blinkRed(5);
    }
  }
#endif

  signalReady();
  Serial.println("الجهاز جاهز — قرب البطاقة...");
}

// ═══════════════════════════════════════════════════════════
void loop() {

  // اعادة الاتصال اذا انقطع الواي فاي
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] انقطع الاتصال — اعادة المحاولة...");
    blinkRed(3);
    connectWiFi();
    return;
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  String uid = getUID();
  unsigned long now = millis();

  // تجاهل نفس البطاقة خلال فترة التبريد
  if (uid == lastUID && (now - lastScanTime) < COOLDOWN_MS) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  lastUID      = uid;
  lastScanTime = now;

  Serial.print("[RFID] بطاقة: ");
  Serial.println(uid);

  sendToServer(uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

// ═══════════════════════════════════════════════════════════
String getUID() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

// ═══════════════════════════════════════════════════════════
void sendToServer(String uid) {
  WiFiClient client;
  HTTPClient http;

  // بناء URL مع باراميترات GET
  String url = "http://" + String(SERVER_IP) + ":" + 
               String(SERVER_PORT) + "/api/scan" +
               "?uid=" + uid +
               "&device_id=" + String(DEVICE_ID) +
               "&device_token=" + deviceToken +
               "&device_role=HALL";

  http.begin(client, url);
  http.setTimeout(HTTP_TIMEOUT);

  Serial.print("[HTTP] إرسال GET... ");
  Serial.println(uid);
  int code = http.GET();
  Serial.print("[HTTP] الجواب: ");
  Serial.println(code);

  if (code == 200) {
    String resp = http.getString();
    Serial.println("[HTTP] " + resp);

    StaticJsonDocument<512> respDoc;
    DeserializationError err = deserializeJson(respDoc, resp);

    if (!err) {
      bool success = respDoc["success"] | false;
      const char* signal = respDoc["signal"] | "";

      if (success) {
        String signalStr = String(signal);
        if (signalStr == "BUZZER_SESSION_OPEN") {
          Serial.println("[OK] الدكتور فتح الجلسة");
          signalSessionOpen();
        } else if (signalStr == "BUZZER_SESSION_CLOSE") {
          Serial.println("[OK] الدكتور أغلق الجلسة");
          signalSessionClose();
        } else {
          const char* name = respDoc["student_name"] | "";
          Serial.print("[OK] تم تسجيل: ");
          Serial.println(name);
          signalSuccess();
        }
      } else {
        const char* error = respDoc["error"] | "unknown";
        Serial.print("[FAIL] مرفوض: ");
        Serial.println(error);

        const char* msg = respDoc["message"] | "";
        if (strlen(msg) > 0) {
          Serial.println(msg);
        }

        String errorStr = String(error);
        if (errorStr == "unauthorized_device") {
          Serial.println("[TOKEN] التوكن غير صالح — جاري التحديث...");
          String newToken = fetchTokenFromServer();
          if (newToken.length() > 0) {
            deviceToken = newToken;
            saveTokenToEEPROM(deviceToken);
            Serial.println("[TOKEN] تم تحديث التوكن — اعادة المحاولة");
            http.end();
            sendToServer(uid);
            return;
          }
        }

        signalError();
      }
    }

  } else if (code == -1) {
    Serial.println("[HTTP] لا يوجد اتصال بالخادم");
    signalError();

  } else if (code == 401) {
    Serial.println("[HTTP] خطأ توكن — جاري التحديث...");
    String newToken = fetchTokenFromServer();
    if (newToken.length() > 0) {
      deviceToken = newToken;
      saveTokenToEEPROM(deviceToken);
      Serial.println("[TOKEN] تم تحديث التوكن — اعادة المحاولة");
      http.end();
      sendToServer(uid);
      return;
    }
    signalError();

  } else {
    Serial.print("[HTTP] خطأ: ");
    Serial.println(code);
    signalError();
  }

  http.end();
}

// ═══════════════════════════════════════════════════════════
void connectWiFi() {
  Serial.print("[WiFi] الاتصال بـ: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  int dots = 0;

  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT) {
      Serial.println("\n[WiFi] فشل الاتصال!");
      blinkRed(5);
      return;
    }
    delay(300);
    Serial.print(".");
    dots++;
    // وميض LED احمر اثناء الانتظار
    digitalWrite(LED_RED, dots % 2);
  }

  digitalWrite(LED_RED, LOW);
  Serial.println("\n[WiFi] متصل!");
  Serial.print("[WiFi] IP: ");
  Serial.println(WiFi.localIP());
}

// ═══════════════════════════════════════════════════════════
//  اشارات LED والبازر
// ═══════════════════════════════════════════════════════════

// حضور مسجل — اخضر + بيب واحد
void signalSuccess() {
  digitalWrite(LED_RED,   LOW);
  digitalWrite(LED_GREEN, HIGH);
  tone(BUZZER_PIN, 1200, 150);
  delay(700);
  digitalWrite(LED_GREEN, LOW);
}

// مرفوض — احمر + بيبين
void signalError() {
  digitalWrite(LED_GREEN, LOW);
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_RED, HIGH);
    tone(BUZZER_PIN, 400, 200);
    delay(280);
    digitalWrite(LED_RED, LOW);
    delay(150);
  }
}

// جاهز — وميض اخضر 3 مرات
void signalReady() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_GREEN, HIGH);
    delay(160);
    digitalWrite(LED_GREEN, LOW);
    delay(160);
  }
}

void signalSessionOpen() {
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_GREEN, HIGH);
  for (int i = 0; i < 3; i++) {
    int freq = 800 + (i * 400);
    tone(BUZZER_PIN, freq, 150);
    delay(200);
  }
  delay(500);
  digitalWrite(LED_GREEN, LOW);
}

void signalSessionClose() {
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, HIGH);
  tone(BUZZER_PIN, 1000, 600);
  delay(700);
  digitalWrite(LED_RED, LOW);
}

// وميض احمر n مرات
void blinkRed(int n) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_RED, HIGH);
    delay(200);
    digitalWrite(LED_RED, LOW);
    delay(200);
  }
}