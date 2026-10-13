#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_INA219.h>
#include <time.h>

// ==============================================================================
// 1. OLED SPI PIN DEFINITIONS (128x64 SPI OLED)
// ==============================================================================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

#define OLED_MOSI  23
#define OLED_CLK   18
#define OLED_DC    21
#define OLED_CS    19
#define OLED_RESET 22

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, OLED_MOSI, OLED_CLK, OLED_DC, OLED_RESET, OLED_CS);

// ==============================================================================
// 2. RELAY PIN DEFINITIONS (Active LOW)
// ==============================================================================
#define RELAY_HOUSE      4   
#define RELAY_INDUSTRY   26  
#define RELAY_STREET     13  
#define RELAY_HOSPITAL   14  

#define RELAY_ON  LOW
#define RELAY_OFF HIGH

// Power Source Sense Pins
#define SMPS1_PIN        34
#define SMPS2_PIN        35
#define BATTERY_PIN      39

// ==============================================================================
// 3. DUAL I2C BUS & INA219 CURRENT/VOLTAGE SENSORS
// ==============================================================================
TwoWire I2C2 = TwoWire(1);

Adafruit_INA219 inaHouse(0x40);     // On Wire (SDA: 27, SCL: 33)
Adafruit_INA219 inaIndustry(0x41);  // On Wire (SDA: 27, SCL: 33)
Adafruit_INA219 inaStreet(0x44);    // On Wire (SDA: 27, SCL: 33)
Adafruit_INA219 inaHospital(0x45);  // On Wire (SDA: 27, SCL: 33)
Adafruit_INA219 inaCritical(0x40);  // On I2C2 (SDA: 25, SCL: 32)

// ==============================================================================
// 4. WIFI & HIVEMQ CLOUD MQTT CREDENTIALS
// ==============================================================================
const char* ssid               = "Verizon-SM-N981U-7692";
const char* password           = "nzjf807(";

const char* mqtt_server        = "78d11d43ac27466695cd0e4f5e7405c8.s1.eu.hivemq.cloud";
const int   mqtt_port          = 8883;
const char* mqtt_user          = "saptarshidas";
const char* mqtt_password      = "saptarshi2007";
const char* mqtt_topic         = "smartgrid/live";
const char* mqtt_control_topic = "smartgrid/control";

WiFiClientSecure espClient;
PubSubClient client(espClient);

// ==============================================================================
// 5. CLOSED-LOOP RELAY STATE TRACKING
// ==============================================================================
bool relay_hospital = true;
bool relay_street   = true;
bool relay_house    = true;
bool relay_industry = true;

char lastActionMsg[32] = "READY (30s OBS)";
unsigned long lastSampleTime = 0;
const unsigned long SAMPLE_INTERVAL = 1000; // 1 sample per second (1 Hz)

// NTP Time formatting helper (UTC+5:30 IST: 19800 seconds)
String getFormattedTimestamp() {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 100)) {
        char buffer[32];
        strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
        return String(buffer);
    }
    // Fallback ISO timestamp with uptime
    char fallback[32];
    unsigned long sec = millis() / 1000;
    snprintf(fallback, sizeof(fallback), "2026-09-13 %02lu:%02lu:%02lu", (sec / 3600) % 24, (sec / 60) % 60, sec % 60);
    return String(fallback);
}

String getUniqueClientID() {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char clientId[32];
    snprintf(clientId, sizeof(clientId), "SMARTGRID_%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(clientId);
}

void applyRelays() {
    digitalWrite(RELAY_HOSPITAL, relay_hospital ? RELAY_ON : RELAY_OFF);
    digitalWrite(RELAY_STREET,   relay_street   ? RELAY_ON : RELAY_OFF);
    digitalWrite(RELAY_HOUSE,    relay_house    ? RELAY_ON : RELAY_OFF);
    digitalWrite(RELAY_INDUSTRY, relay_industry ? RELAY_ON : RELAY_OFF);
}

// ==============================================================================
// 6. CLOSED-LOOP ACTUATOR CALLBACK (RECEIVES AI COMMANDS FROM LAPTOP)
// ==============================================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) {
        Serial.printf("[ACTUATOR ERROR] Failed to parse JSON command: %s\n", err.c_str());
        return;
    }

    const char* cmd    = doc["cmd"] | "";
    const char* load   = doc["load"] | "";
    int state          = doc["state"] | -1;
    const char* reason = doc["reason"] | "";

    Serial.printf("\n>>> [AI ACTUATOR RECEIVED] CMD: %s | LOAD: %s | STATE: %d | REASON: %s <<<\n",
                  cmd, load, state, reason);

    if (state == 0 || state == 1) {
        bool targetState = (state == 1);
        uint8_t pinVal = targetState ? RELAY_ON : RELAY_OFF;

        if (strcasecmp(load, "hospital") == 0) {
            relay_hospital = targetState;
            digitalWrite(RELAY_HOSPITAL, pinVal);
        } else if (strcasecmp(load, "street") == 0) {
            relay_street = targetState;
            digitalWrite(RELAY_STREET, pinVal);
        } else if (strcasecmp(load, "house") == 0) {
            relay_house = targetState;
            digitalWrite(RELAY_HOUSE, pinVal);
        } else if (strcasecmp(load, "industry") == 0) {
            relay_industry = targetState;
            digitalWrite(RELAY_INDUSTRY, pinVal);
        }
        snprintf(lastActionMsg, sizeof(lastActionMsg), "%s %s", cmd, load);
    }
}

void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);
    WiFi.begin(ssid, password);
}

void reconnectMQTT() {
    if (WiFi.status() != WL_CONNECTED) return;
    if (!client.connected()) {
        String clientId = getUniqueClientID();
        if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
            Serial.println("[MQTT] Connected to HiveMQ Cloud broker successfully!");
            client.subscribe(mqtt_control_topic);
            Serial.printf("[MQTT] Subscribed to closed-loop actuator topic: %s\n", mqtt_control_topic);
        }
    }
}

// ==============================================================================
// 2-SD LOCAL OVERCURRENT LIMITS & OFFLINE AUTONOMOUS PROTECTION
// ==============================================================================
const float THRESH_HOSPITAL = 272.0;
const float THRESH_STREET   = 405.0;
const float THRESH_HOUSE    = 256.0;
const float THRESH_INDUSTRY = 264.0;
const float THRESH_CRITICAL = 320.0;

void evaluateLocalAutonomousProtection(float c_crit, float c_hosp, float c_str, float c_hou, float c_ind, float tot_mA, float limit_mA) {
    bool cloudActive = (WiFi.status() == WL_CONNECTED && client.connected());

    // 1. Instant 2-SD Overcurrent Protection (Local Hardware Breaker)
    // Always active: trips dangerous overcurrent in < 1 sec even if Wi-Fi is completely dead!
    if (c_hosp > THRESH_HOSPITAL && relay_hospital) {
        relay_hospital = false;
        digitalWrite(RELAY_HOSPITAL, RELAY_OFF);
        snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL TRIP HOSP");
        Serial.printf(">>> [LOCAL EDGE TRIP] Hospital Overcurrent: %.1f mA > %.1f mA <<<\n", c_hosp, THRESH_HOSPITAL);
    }
    if (c_str > THRESH_STREET && relay_street) {
        relay_street = false;
        digitalWrite(RELAY_STREET, RELAY_OFF);
        snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL TRIP STRT");
        Serial.printf(">>> [LOCAL EDGE TRIP] Street Overcurrent: %.1f mA > %.1f mA <<<\n", c_str, THRESH_STREET);
    }
    if (c_hou > THRESH_HOUSE && relay_house) {
        relay_house = false;
        digitalWrite(RELAY_HOUSE, RELAY_OFF);
        snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL TRIP HOUS");
        Serial.printf(">>> [LOCAL EDGE TRIP] House Overcurrent: %.1f mA > %.1f mA <<<\n", c_hou, THRESH_HOUSE);
    }
    if (c_ind > THRESH_INDUSTRY && relay_industry) {
        relay_industry = false;
        digitalWrite(RELAY_INDUSTRY, RELAY_OFF);
        snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL TRIP INDU");
        Serial.printf(">>> [LOCAL EDGE TRIP] Industry Overcurrent: %.1f mA > %.1f mA <<<\n", c_ind, THRESH_INDUSTRY);
    }

    // 2. Local Fallback Capacity Shedding when OFFLINE (Wi-Fi or Cloud is down)
    // If offline and utilization >= 85% of power limit, shed lowest priority load:
    // Industry (1) -> House (2) -> Street (3) -> Hospital (4)
    if (!cloudActive && limit_mA > 0 && tot_mA >= (0.85 * limit_mA)) {
        if (relay_industry) {
            relay_industry = false;
            digitalWrite(RELAY_INDUSTRY, RELAY_OFF);
            snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL SHED INDU");
            Serial.printf(">>> [LOCAL OFFLINE SHED] Industry shed at %.1f mA (>= 85%% of %.0f mA) <<<\n", tot_mA, limit_mA);
        } else if (relay_house) {
            relay_house = false;
            digitalWrite(RELAY_HOUSE, RELAY_OFF);
            snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL SHED HOUS");
            Serial.printf(">>> [LOCAL OFFLINE SHED] House shed at %.1f mA (>= 85%% of %.0f mA) <<<\n", tot_mA, limit_mA);
        } else if (relay_street) {
            relay_street = false;
            digitalWrite(RELAY_STREET, RELAY_OFF);
            snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL SHED STRT");
            Serial.printf(">>> [LOCAL OFFLINE SHED] Street shed at %.1f mA (>= 85%% of %.0f mA) <<<\n", tot_mA, limit_mA);
        }
    }
}

void safeRead(TwoWire &bus, Adafruit_INA219 &sensor, uint8_t addr, float &voltage, float &current_mA, float &power_mW, bool &ok) {
    bus.beginTransmission(addr);
    if (bus.endTransmission() != 0) {
        ok = false;
        voltage = 0.0; current_mA = 0.0; power_mW = 0.0;
        return;
    }

    voltage = sensor.getBusVoltage_V();
    current_mA = sensor.getCurrent_mA();

    if (isnan(voltage) || isnan(current_mA)) {
        ok = false;
        voltage = 0.0; current_mA = 0.0; power_mW = 0.0;
    } else {
        ok = true;
        if (current_mA > -0.5 && current_mA < 0.5) current_mA = 0.0;
        power_mW = voltage * current_mA;
    }
}

void updateOLED(const char* modeStr, float limit_mA,
                float c_crit, float c_hosp, float c_str, float c_hou, float c_ind, float tot_mA) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    bool wifiOk = (WiFi.status() == WL_CONNECTED);
    bool mqttOk = client.connected();
    const char* netTag = (wifiOk && mqttOk) ? "CLOUD" : (wifiOk ? "NO-MQTT" : "OFFLINE");

    display.setCursor(0, 0);
    display.printf("%s|%4.0f|%s", modeStr, limit_mA, netTag);

    display.setCursor(0, 11);
    display.printf("HOS: %4.0fmA STR: %4.0fmA", c_hosp, c_str);

    display.setCursor(0, 22);
    display.printf("HOU: %4.0fmA IND: %4.0fmA", c_hou, c_ind);

    display.setCursor(0, 33);
    display.printf("CRI: %4.0fmA TOT:%5.0fmA", c_crit, tot_mA);

    display.setCursor(0, 44);
    display.printf("RLY:[%d%d%d%d] (%s)", 
                   relay_hospital ? 1 : 0, 
                   relay_street   ? 1 : 0, 
                   relay_house    ? 1 : 0, 
                   relay_industry ? 1 : 0,
                   (tot_mA > (0.85 * limit_mA)) ? "SHED" : "NORM");

    display.setCursor(0, 55);
    display.printf("ACT: %s", lastActionMsg);

    display.display();
}

// ==============================================================================
// 7. SETUP
// ==============================================================================
void setup() {
    Serial.begin(115200);
    delay(500);

    // Initialize Relays (All ON for 30s observation phase)
    pinMode(RELAY_HOSPITAL, OUTPUT);
    pinMode(RELAY_STREET,   OUTPUT);
    pinMode(RELAY_HOUSE,    OUTPUT);
    pinMode(RELAY_INDUSTRY, OUTPUT);

    relay_hospital = true;
    relay_street   = true;
    relay_house    = true;
    relay_industry = true;
    applyRelays();

    // Source inputs
    pinMode(SMPS1_PIN, INPUT);
    pinMode(SMPS2_PIN, INPUT);
    pinMode(BATTERY_PIN, INPUT);

    // OLED Init
    display.begin(SSD1306_SWITCHCAPVCC);
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 15);
    display.println("SMART GRID AI");
    display.setCursor(0, 30);
    display.println("Closed-Loop Actuator");
    display.setCursor(0, 45);
    display.println("Connecting WiFi...");
    display.display();

    // Dual I2C Init
    Wire.begin(27, 33);
    Wire.setTimeOut(50);
    I2C2.begin(25, 32);
    I2C2.setTimeOut(50);

    inaHospital.begin(&Wire);
    inaStreet.begin(&Wire);
    inaHouse.begin(&Wire);
    inaIndustry.begin(&Wire);
    inaCritical.begin(&I2C2);

    // MQTT Client Configuration
    espClient.setInsecure();
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(mqttCallback);
    client.setBufferSize(1024);

    connectWiFi();
    // Synchronize NTP clock (UTC+5:30 IST = 19800s)
    configTime(19800, 0, "pool.ntp.org", "time.google.com");

    Serial.println("\n==================================================================");
    Serial.println("  ⚡ ESP32 AUTONOMOUS CLOSED-LOOP SMART GRID ACTUATOR ⚡");
    Serial.println("  Operating Mode : CLOSED-LOOP (NO Dataset Logging / NO Combos)");
    Serial.println("  Relays at Boot : [ALL 4 ON for 30s Observation Window]");
    Serial.printf("  Telemetry Topic: %s\n", mqtt_topic);
    Serial.printf("  Actuator Topic : %s\n", mqtt_control_topic);
    Serial.println("==================================================================");
}

// ==============================================================================
// 8. MAIN LOOP
// ==============================================================================
void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        if (!client.connected()) reconnectMQTT();
        client.loop();
    } else {
        // Non-blocking Wi-Fi auto-reconnection attempt every 5 seconds
        static unsigned long lastWifiRetry = 0;
        if (millis() - lastWifiRetry >= 5000) {
            lastWifiRetry = millis();
            Serial.println("[WIFI] Offline. Retrying connection...");
            WiFi.reconnect();
        }
    }

    if (millis() - lastSampleTime >= SAMPLE_INTERVAL) {
        lastSampleTime = millis();

        int smps1 = digitalRead(SMPS1_PIN);
        int smps2 = digitalRead(SMPS2_PIN);
        int battery = digitalRead(BATTERY_PIN);

        const char* modeStr = "DUAL SMPS";
        float current_limit = 5000.0;
        if (smps1 && smps2) {
            modeStr = "DUAL SMPS";
            current_limit = 5000.0;
        } else if (smps1 || smps2) {
            modeStr = "SINGLE SMPS";
            current_limit = 1000.0;
        } else if (battery) {
            modeStr = "BATTERY";
            current_limit = 800.0;
        }

        float v_crit = 0, c_crit = 0, p_crit = 0;
        float v_hosp = 0, c_hosp = 0, p_hosp = 0;
        float v_str  = 0, c_str  = 0, p_str  = 0;
        float v_hou  = 0, c_hou  = 0, p_hou  = 0;
        float v_ind  = 0, c_ind  = 0, p_ind  = 0;

        bool ok_crit, ok_hosp, ok_str, ok_hou, ok_ind;

        safeRead(I2C2, inaCritical, 0x40, v_crit, c_crit, p_crit, ok_crit);
        safeRead(Wire, inaHospital, 0x45, v_hosp, c_hosp, p_hosp, ok_hosp);
        safeRead(Wire, inaStreet,   0x44, v_str,  c_str,  p_str,  ok_str);
        safeRead(Wire, inaHouse,    0x40, v_hou,  c_hou,  p_hou,  ok_hou);
        safeRead(Wire, inaIndustry, 0x41, v_ind,  c_ind,  p_ind,  ok_ind);

        float total_mA = c_crit + c_hosp + c_str + c_hou + c_ind;
        float total_mW = p_crit + p_hosp + p_str + p_hou + p_ind;

        // Autonomous Local Edge Protection (Runs locally on ESP32 regardless of Wi-Fi state)
        evaluateLocalAutonomousProtection(c_crit, c_hosp, c_str, c_hou, c_ind, total_mA, current_limit);

        // Re-read physical relay states after potential local trip/shed
        int r_hosp = (digitalRead(RELAY_HOSPITAL) == RELAY_ON) ? 1 : 0;
        int r_str  = (digitalRead(RELAY_STREET)   == RELAY_ON) ? 1 : 0;
        int r_hou  = (digitalRead(RELAY_HOUSE)    == RELAY_ON) ? 1 : 0;
        int r_ind  = (digitalRead(RELAY_INDUSTRY) == RELAY_ON) ? 1 : 0;

        // Publish JSON telemetry packet if connected
        if (client.connected()) {
            JsonDocument doc;
            doc["timestamp"]     = getFormattedTimestamp();
            doc["device_id"]     = "ESP32_SMARTGRID";
            doc["firmware"]      = "2.0.0-closed-loop";
            doc["hardware"]      = "ESP32";
            doc["location"]      = "Lab";
            doc["group"]         = "Group A";
            doc["wifi_rssi"]     = WiFi.RSSI();
            doc["uptime"]        = (unsigned long)(millis() / 1000);
            doc["mode"]          = modeStr;
            doc["current_limit"] = current_limit;

            JsonObject sources = doc["sources"].to<JsonObject>();
            sources["smps1"]   = (bool)smps1;
            sources["smps2"]   = (bool)smps2;
            sources["battery"] = (bool)battery;

            JsonObject crit = doc["critical"].to<JsonObject>();
            crit["voltage"] = v_crit;
            crit["current"] = c_crit;
            crit["power"]   = p_crit;

            JsonArray loads = doc["loads"].to<JsonArray>();

            JsonObject hospObj = loads.add<JsonObject>();
            hospObj["name"]            = "Hospital";
            hospObj["voltage"]         = v_hosp;
            hospObj["current"]         = c_hosp;
            hospObj["power"]           = p_hosp;
            hospObj["relay"]           = (bool)r_hosp;
            hospObj["priority"]        = 4;
            hospObj["fault"]           = 0;
            hospObj["nominal_current"] = 256.0;

            JsonObject strObj = loads.add<JsonObject>();
            strObj["name"]            = "Street";
            strObj["voltage"]         = v_str;
            strObj["current"]         = c_str;
            strObj["power"]           = p_str;
            strObj["relay"]           = (bool)r_str;
            strObj["priority"]        = 3;
            strObj["fault"]           = 0;
            strObj["nominal_current"] = 394.0;

            JsonObject houObj = loads.add<JsonObject>();
            houObj["name"]            = "House";
            houObj["voltage"]         = v_hou;
            houObj["current"]         = c_hou;
            houObj["power"]           = p_hou;
            houObj["relay"]           = (bool)r_hou;
            houObj["priority"]        = 2;
            houObj["fault"]           = 0;
            houObj["nominal_current"] = 241.0;

            JsonObject indObj = loads.add<JsonObject>();
            indObj["name"]            = "Industry";
            indObj["voltage"]         = v_ind;
            indObj["current"]         = c_ind;
            indObj["power"]           = p_ind;
            indObj["relay"]           = (bool)r_ind;
            indObj["priority"]        = 1;
            indObj["fault"]           = 0;
            indObj["nominal_current"] = 240.0;

            JsonObject totals = doc["totals"].to<JsonObject>();
            totals["current"] = total_mA;
            totals["power"]   = total_mW;

            char jsonBuffer[1024];
            size_t len = serializeJson(doc, jsonBuffer);
            client.publish(mqtt_topic, jsonBuffer, len);
        }

        // Serial log
        Serial.printf("[GRID TELEMETRY] Limit: %.0f mA | Total: %.1f mA | RLY:[%d%d%d%d] | Action: %s\n",
                      current_limit, total_mA, r_hosp, r_str, r_hou, r_ind, lastActionMsg);

        // Update OLED
        updateOLED(modeStr, current_limit, c_crit, c_hosp, c_str, c_hou, c_ind, total_mA);
    }
}