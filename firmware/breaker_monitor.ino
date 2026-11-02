// Smart Breaker Monitor - ESP32 firmware (Arduino framework)
// Reads current/voltage, drives a relay that stands in for the breaker, trips on overload,
// counts operations (endurance), and sends real-time data over Wi-Fi to the dashboard server.
#include <WiFi.h>
#include <HTTPClient.h>

// ---- configure these ----
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* SERVER    = "http://192.168.1.50:8000";   // PC running server/app.py
// -------------------------

#define RELAY_PIN    26     // relay module = breaker contact
#define CURRENT_PIN  34     // ACS712 (or similar) analog output
#define VOLTAGE_PIN  35     // ZMPT101B (or similar) analog output
#define USE_SENSORS  false  // false = simulated readings, true = read the analog sensors
const float TRIP_CURRENT_A = 15.0;
const unsigned long SEND_MS = 1000;

bool closedState = true;
int  opCount = 0, trips = 0;
unsigned long lastSend = 0;

float readCurrent() {
  if (!USE_SENSORS) return closedState ? 5.0 + (random(-40, 40) / 100.0) : 0.0;
  // ACS712-20A: 2.5 V at 0 A, 100 mV/A (after divider to 3.3 V ADC). Adjust to your module.
  long sum = 0; for (int i = 0; i < 200; i++) sum += analogRead(CURRENT_PIN);
  float v = (sum / 200.0) * 3.3 / 4095.0;
  return closedState ? fabs((v - 1.65) / 0.066) : 0.0;
}
float readVoltage() {
  if (!USE_SENSORS) return 230.0 + (random(-20, 20) / 10.0);
  long sum = 0; for (int i = 0; i < 200; i++) sum += analogRead(VOLTAGE_PIN);
  return (sum / 200.0) * 3.3 / 4095.0 * 100.0;       // calibrate scale factor for your sensor
}
void setBreaker(bool close) {
  if (close == closedState) return;
  closedState = close; opCount++;
  digitalWrite(RELAY_PIN, closedState ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT); digitalWrite(RELAY_PIN, HIGH);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.printf("\nWi-Fi connected, IP %s\n", WiFi.localIP().toString().c_str());
}

void loop() {
  float amps = readCurrent();
  if (closedState && amps > TRIP_CURRENT_A) {        // overload protection
    setBreaker(false); trips++; amps = 0;
    Serial.println("OVERLOAD - breaker tripped");
  }
  if (millis() - lastSend >= SEND_MS && WiFi.status() == WL_CONNECTED) {
    lastSend = millis();
    char body[160];
    snprintf(body, sizeof(body),
      "{\"current\":%.2f,\"voltage\":%.1f,\"state\":\"%s\",\"op_count\":%d,\"trips\":%d}",
      amps, readVoltage(), closedState ? "closed" : "open", opCount, trips);
    HTTPClient http;
    http.begin(String(SERVER) + "/api/telemetry");
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(body);
    if (code == 200) {                               // server replies {"command":"open"|"close"|null}
      String r = http.getString();
      if (r.indexOf("\"open\"") >= 0)       setBreaker(false);
      else if (r.indexOf("\"close\"") >= 0) setBreaker(true);
    } else Serial.printf("POST failed: %d\n", code);
    http.end();
  }
}
