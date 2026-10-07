/*
 * ============================================================
 *  سكانر السكرتارية — NodeMCU ESP8266 (WiFi)
 *  مبني على نفس بنية scanner_hall الشغّال
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
 *  LED الأخضر  → D2  (GPIO4)
 *  LED الأحمر  → D3  (GPIO0)
 *  بازر        → D4  (GPIO2)  — اختياري
 *
 *  المكتبات المطلوبة:
 *  - MFRC522 by GithubCommunity
 * ============================================================
 *
 *  الوظيفة:
 *  - تمرير بطاقة → إرسال UID إلى /api/scan/register-card
 *  - تظهر فوراً في حقل تسجيل الطالب/الدكتور بالواجهة
 *  - بدون توكن (هاد قارئ تسجيل فقط)
 * ============================================================
 */

#include <SPI.h>
#include <MFRC522.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

// ══════════════════════════════════════════
//  اعدل هذه القيم فقط
// ══════════════════════════════════════════
//  يجب أن يكون NodeMCU والكمبيوتر على نفس شبكة Wi-Fi
#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"
#define SERVER_IP      "YOUR_SERVER_IP"
#define SERVER_PORT    5000
// ══════════════════════════════════════════

#define SS_PIN   15   // D8
#define RST_PIN   5   // D1

#define LED_GREEN   4   // D2
#define LED_RED     0   // D3
#define BUZZER_PIN  2   // D4

#define COOLDOWN_MS    2000
#define WIFI_TIMEOUT   15000

MFRC522 rfid(SS_PIN, RST_PIN);

String   lastUID      = "";
unsigned long lastScanTime = 0;

// ════════════════════════════════════════════
//  Setup
// ════════════════════════════════════════════
void setup() {
  Serial.begin(9600);
  delay(300);

  Serial.println();
  Serial.println("================================");
  Serial.println("  سكانر السكرتارية");
  Serial.println("================================");

  pinMode(LED_GREEN,  OUTPUT);
  pinMode(LED_RED,    OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED,   LOW);
  digitalWrite(BUZZER_PIN, LOW);

  SPI.begin();
  rfid.PCD_Init();
  delay(100);

  // التحقق من القارئ
  byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  Serial.print("[RFID] إصدار MFRC522: 0x");
  Serial.println(v, HEX);
  if (v == 0x00 || v == 0xFF) {
    Serial.println("[!] خطأ: تحقق من توصيلات MFRC522");
    blinkRed(5);
  }

  // اتصال WiFi
  connectWiFi();

  Serial.println("[READY] قرّب البطاقة...");
  blinkGreen(2);
}

// ════════════════════════════════════════════
//  WiFi
// ════════════════════════════════════════════
void connectWiFi() {
  Serial.print("[WiFi] الاتصال بـ ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT) {
    digitalWrite(LED_GREEN, !digitalRead(LED_GREEN));
    delay(250);
    Serial.print(".");
  }
  digitalWrite(LED_GREEN, LOW);

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("[WiFi] متصل!");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("[WiFi] فشل الاتصال!");
    blinkRed(3);
  }
}

// ════════════════════════════════════════════
//  Loop
// ════════════════════════════════════════════
void loop() {
  // إعادة الاتصال إذا انقطع
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] انقطع — إعادة الاتصال...");
    connectWiFi();
    delay(500);
    return;
  }

  // فحص بطاقة جديدة
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  String uid = getUID();
  unsigned long now = millis();

  // منع تكرار نفس البطاقة خلال ثانيتين
  if (uid == lastUID && (now - lastScanTime) < COOLDOWN_MS) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }
  lastUID      = uid;
  lastScanTime = now;

  Serial.println();
  Serial.print("[RFID] بطاقة: ");
  Serial.println(uid);

  // إرسال للسيرفر
  if (sendUID(uid)) {
    Serial.println("[OK] الـ UID جاهز في الواجهة");
    signalGreen();
  } else {
    Serial.println("[ERR] فشل الإرسال");
    signalRed();
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

// ════════════════════════════════════════════
//  إرسال للسيرفر
// ════════════════════════════════════════════
bool sendUID(String uid) {
  WiFiClient client;
  HTTPClient http;

  String url = "http://" + String(SERVER_IP) + ":" +
               String(SERVER_PORT) + "/api/scan/register-card";

  Serial.print("[HTTP] POST ");
  Serial.println(url);

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  String body = "{\"uid\":\"" + uid + "\",\"device_id\":\"SECRETARY\",\"device_role\":\"SECRETARY\"}";

  int code = http.POST(body);
  Serial.print("[HTTP] الجواب: ");
  Serial.println(code);

  bool ok = (code == 200 || code == 201);
  if (code <= 0) {
    Serial.println("[HTTP] لا اتصال — تحقق من IP والـ Firewall");
  }
  http.end();
  return ok;
}

// ════════════════════════════════════════════
//  Helpers
// ════════════════════════════════════════════
String getUID() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

void signalGreen() {
  digitalWrite(LED_GREEN, HIGH);
  beep(1500, 100);
  delay(300);
  digitalWrite(LED_GREEN, LOW);
}

void signalRed() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_RED, HIGH);
    beep(400, 80);
    delay(100);
    digitalWrite(LED_RED, LOW);
    delay(80);
  }
}

void blinkGreen(int n) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_GREEN, HIGH);
    delay(120);
    digitalWrite(LED_GREEN, LOW);
    delay(120);
  }
}

void blinkRed(int n) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED_RED, HIGH);
    delay(150);
    digitalWrite(LED_RED, LOW);
    delay(150);
  }
}

void beep(int freq, int dur) {
  // استخدام tone() المدمجة في ESP8266 — آمنة ولا تسبب reboot
  tone(BUZZER_PIN, freq, dur);
  delay(dur + 10);
  noTone(BUZZER_PIN);
}
