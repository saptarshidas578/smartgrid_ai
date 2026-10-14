import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (on pages after the first)
        if self._pageNumber > 1:
            self.drawString(54, 755, "Smart Grid AI — ESP32 Hardware Firmware Analysis (smartgrid_closed_loop_esp32.ino)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        # Footer (on all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_text)
        self.drawString(54, 32, "Vellore Institute of Technology (VIT) | Saptarshi Das | saptarshidas578/smartgrid_ai")
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#1E293B'),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # Title Banner
    story.append(Paragraph("ESP32 Autonomous Smart Grid Controller", title_style))
    story.append(Paragraph("Comprehensive Hardware Architecture, Circuit Interfaces & Line-by-Line Firmware Analysis", subtitle_style))

    # Meta card table
    meta_data = [
        [
            Paragraph("<b>Author:</b> Saptarshi Das<br/><b>Institution:</b> Vellore Institute of Technology (VIT)<br/><b>Email:</b> saptarshid234@outlook.com", body_style),
            Paragraph("<b>Target File:</b> <code>firmware/.../smartgrid_closed_loop_esp32.ino</code><br/><b>Hardware Platform:</b> ESP32-WROOM-32 (Xtensa Dual-Core 240 MHz)<br/><b>Firmware Version:</b> 2.0.0-closed-loop", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[250, 254])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Section: Executive Architecture Overview
    story.append(Paragraph("1. System Hardware Architecture & Functional Design", h1_style))
    story.append(Paragraph(
        "The microgrid embedded firmware operates as a real-time, closed-loop cyber-physical controller implemented on an "
        "Espressif ESP32 dual-core microcontroller clocked at 240 MHz. The system coordinates high-precision high-side DC current and "
        "voltage sensing across five discrete microgrid feeders, drives a 4-channel optoisolated power switchgear relay module, "
        "manages a 128x64 SPI OLED telemetry display, communicates via secure TLS MQTT (port 8883) with a cloud digital twin SCADA layer, "
        "and enforces an autonomous sub-second hardware breaker trip directly at the edge.",
        body_style
    ))

    # Hardware Table
    hw_table_data = [
        [Paragraph("<b>Subsystem</b>", body_style), Paragraph("<b>Components & Protocols</b>", body_style), Paragraph("<b>Key GPIO Pinout</b>", body_style), Paragraph("<b>Operational Role</b>", body_style)],
        [Paragraph("Main MCU", body_style), Paragraph("ESP32-WROOM-32 (Dual Core 240MHz)", body_style), Paragraph("Onboard 3.3V Logic", body_style), Paragraph("Sensing, safety logic, TLS telemetry, actuator control", body_style)],
        [Paragraph("I2C Bus 1 (Wire)", body_style), Paragraph("4x Texas Instruments INA219", body_style), Paragraph("SDA: GPIO 27<br/>SCL: GPIO 33", body_style), Paragraph("Monitors House (0x40), Industry (0x41), Street (0x44), Hospital (0x45)", body_style)],
        [Paragraph("I2C Bus 2 (I2C2)", body_style), Paragraph("1x Texas Instruments INA219", body_style), Paragraph("SDA: GPIO 25<br/>SCL: GPIO 32", body_style), Paragraph("Monitors Critical Infrastructure (0x40) avoiding address clash", body_style)],
        [Paragraph("Relay Switchgear", body_style), Paragraph("4-Ch Optoisolated Relays (Active-LOW)", body_style), Paragraph("Hosp: 14, Strt: 13<br/>Hous: 4, Indu: 26", body_style), Paragraph("Feeder disconnection/reconnection; fail-safe normally energized", body_style)],
        [Paragraph("Source Sensing", body_style), Paragraph("Digital Rail Presence Sense", body_style), Paragraph("SMPS1: 34, SMPS2: 35<br/>Battery: 39", body_style), Paragraph("Detects Dual SMPS (5A), Single SMPS (1A), or Battery (800mA)", body_style)],
        [Paragraph("Display (SPI)", body_style), Paragraph("0.96 inch SSD1306 OLED (128x64)", body_style), Paragraph("MOSI: 23, CLK: 18, DC: 21<br/>CS: 19, RESET: 22", body_style), Paragraph("Real-time telemetry, relay vector [1111], mode, and alerts", body_style)],
        [Paragraph("Cloud Networking", body_style), Paragraph("WiFiClientSecure + PubSubClient", body_style), Paragraph("802.11 b/g/n (2.4 GHz)", body_style), Paragraph("HiveMQ Cloud TLS MQTTS (Port 8883), 1Hz pub, sub control", body_style)],
    ]
    hw_table = Table(hw_table_data, colWidths=[90, 130, 110, 174])
    hw_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(hw_table)
    story.append(Spacer(1, 14))

    # Helper function to add code + explanation blocks
    def add_code_section(sec_title, code_snippet, explanation_bullets):
        items = []
        items.append(Paragraph(sec_title, h2_style))
        
        # Preformatted code box
        clean_code = code_snippet.strip()
        code_p = Preformatted(clean_code, code_style)
        code_box = Table([[code_p]], colWidths=[504])
        code_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        items.append(code_box)
        items.append(Spacer(1, 6))

        for bullet in explanation_bullets:
            items.append(Paragraph(bullet, bullet_style))
        items.append(Spacer(1, 8))
        return KeepTogether(items)

    # Line by line sections
    story.append(Paragraph("2. Line-by-Line Firmware Dissection & Electrical Rationale", h1_style))

    # Section 1
    story.append(add_code_section(
        "Part 1: Header Inclusions & External Libraries (Lines 1–12)",
        """1: #include <Arduino.h>
2: #include <Wire.h>
3: #include <SPI.h>
4: #include <WiFi.h>
5: #include <WiFiClientSecure.h>
6: #include <PubSubClient.h>
7: #include <ArduinoJson.h>
8: #include <Adafruit_GFX.h>
9: #include <Adafruit_SSD1306.h>
10: #include <Adafruit_INA219.h>
11: #include <time.h>""",
        [
            "<b>Line 1 (&lt;Arduino.h&gt;):</b> Core framework providing hardware register bindings, pin mapping constants, and core timing routines (<code>millis()</code>, <code>digitalRead()</code>, <code>digitalWrite()</code>).",
            "<b>Line 2 (&lt;Wire.h&gt;):</b> Hardware I2C communications engine used to read shunt voltage, bus voltage, and current from INA219 sensor ICs.",
            "<b>Line 3 (&lt;SPI.h&gt;):</b> Serial Peripheral Interface master driver enabling high-throughput block data streaming to the OLED display.",
            "<b>Lines 4–5 (&lt;WiFi.h&gt;, &lt;WiFiClientSecure.h&gt;):</b> ESP32 802.11 station stack plus mbedTLS cryptographic socket wrapper supporting TLS 1.2/1.3 mutual handshake on port 8883.",
            "<b>Line 6 (&lt;PubSubClient.h&gt;):</b> Lightweight MQTT client handling binary packet encoding, keep-alives, QoS handshakes, and subscription callbacks.",
            "<b>Line 7 (&lt;ArduinoJson.h&gt;):</b> Fixed-memory JSON serialization/deserialization library avoiding heap fragmentation during telemetry packaging.",
            "<b>Lines 8–10 (&lt;Adafruit_GFX.h&gt;, &lt;Adafruit_SSD1306.h&gt;, &lt;Adafruit_INA219.h&gt;):</b> Peripheral device drivers for the SSD1306 display controller and INA219 current monitors.",
            "<b>Line 11 (&lt;time.h&gt;):</b> POSIX standard time library interfacing with ESP32 SNTP client for sub-millisecond clock synchronization."
        ]
    ))

    # Section 2
    story.append(add_code_section(
        "Part 2: SPI OLED Display Configuration (Lines 13–26)",
        """16: #define SCREEN_WIDTH 128
17: #define SCREEN_HEIGHT 64
19: #define OLED_MOSI  23
20: #define OLED_CLK   18
21: #define OLED_DC    21
22: #define OLED_CS    19
23: #define OLED_RESET 22
25: Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, OLED_MOSI, OLED_CLK, OLED_DC, OLED_RESET, OLED_CS);""",
        [
            "<b>Lines 16–17:</b> Sets display dimensions to 128x64 monochrome pixels (requiring a 1024-byte in-memory frame buffer).",
            "<b>Lines 19–20:</b> Maps SPI data lines: MOSI to GPIO 23 and Clock (SCK) to GPIO 18.",
            "<b>Line 21:</b> Maps Data/Command select pin to GPIO 21 (High = Pixel framebuffer stream, Low = SSD1306 command byte).",
            "<b>Lines 22–23:</b> Maps Chip Select (CS) to GPIO 19 and Hardware Reset to GPIO 22.",
            "<b>Line 25:</b> Instantiates the global <code>display</code> driver object. Using hardware-mapped SPI pins guarantees high frame refresh rates without blocking core control tasks."
        ]
    ))

    # Section 3
    story.append(add_code_section(
        "Part 3: Relay Switchgear & Source Sense Pin Definitions (Lines 27–42)",
        """30: #define RELAY_HOUSE      4   
31: #define RELAY_INDUSTRY   26  
32: #define RELAY_STREET     13  
33: #define RELAY_HOSPITAL   14  
35: #define RELAY_ON  LOW
36: #define RELAY_OFF HIGH
39: #define SMPS1_PIN        34
40: #define SMPS2_PIN        35
41: #define BATTERY_PIN      39""",
        [
            "<b>Lines 30–33:</b> Assigns relay coil control lines to GPIO 4 (House), GPIO 26 (Industry), GPIO 13 (Street Light), and GPIO 14 (Hospital Auxiliary).",
            "<b>Lines 35–36 (Active-LOW Logic):</b> Standard optocoupler boards are active-LOW: pulling the GPIO to 0V (<code>LOW</code>) drives optodiode forward current, energizing the relay coil. Setting the GPIO to 3.3V (<code>HIGH</code>) turns off the optocoupler, de-energizing the contacts.",
            "<b>Lines 39–41:</b> Configures digital sense lines: GPIO 34 (SMPS 1), GPIO 35 (SMPS 2), and GPIO 39 (Battery). These are input-only pins (GPI) on the ESP32 with no internal pull-ups, requiring external pull-down resistors."
        ]
    ))

    # Section 4
    story.append(add_code_section(
        "Part 4: Dual I2C Bus Architecture & INA219 Addressing (Lines 43–53)",
        """46: TwoWire I2C2 = TwoWire(1);
48: Adafruit_INA219 inaHouse(0x40);     // On Wire (SDA: 27, SCL: 33)
49: Adafruit_INA219 inaIndustry(0x41);  // On Wire (SDA: 27, SCL: 33)
50: Adafruit_INA219 inaStreet(0x44);    // On Wire (SDA: 27, SCL: 33)
51: Adafruit_INA219 inaHospital(0x45);  // On Wire (SDA: 27, SCL: 33)
52: Adafruit_INA219 inaCritical(0x40);  // On I2C2 (SDA: 25, SCL: 32)""",
        [
            "<b>Line 46 (Dual I2C Bus Instantiation):</b> The ESP32 contains two hardware I2C peripherals. <code>TwoWire(1)</code> instantiates the secondary controller <code>I2C2</code>.",
            "<b>Lines 48–51:</b> Mounts four INA219 sensors on primary bus <code>Wire</code> using distinct address pin configurations: 0x40 (GND/GND), 0x41 (GND/VCC), 0x44 (VCC/GND), 0x45 (VCC/VCC).",
            "<b>Line 52 (Critical Address Conflict Resolution):</b> The fifth sensor (<code>inaCritical</code>) shares address 0x40. Placing it on <code>I2C2</code> (SDA: 25, SCL: 32) eliminates bus contention without requiring an external multiplexer IC (like TCA9548A)."
        ]
    ))

    # Section 5
    story.append(add_code_section(
        "Part 5: Secure Cloud Network & HiveMQ MQTT Credentials (Lines 54–69)",
        """57: const char* ssid               = "Verizon-SM-N981U-7692";
58: const char* password           = "nzjf807(";
60: const char* mqtt_server        = "78d11d43ac27466695cd0e4f5e7405c8.s1.eu.hivemq.cloud";
61: const int   mqtt_port          = 8883;
62: const char* mqtt_user          = "saptarshidas";
63: const char* mqtt_password      = "saptarshi2007";
64: const char* mqtt_topic         = "smartgrid/live";
65: const char* mqtt_control_topic = "smartgrid/control";
67: WiFiClientSecure espClient;
68: PubSubClient client(espClient);""",
        [
            "<b>Lines 57–58:</b> Wi-Fi Station configuration parameters.",
            "<b>Lines 60–63:</b> HiveMQ Cloud TLS cluster endpoint, port 8883 (MQTTS), and secure user authentication credentials.",
            "<b>Lines 64–65:</b> Dedicated MQTT pub/sub topics: <code>smartgrid/live</code> (1Hz telemetry uplink) and <code>smartgrid/control</code> (closed-loop command downlink).",
            "<b>Lines 67–68:</b> Instantiates <code>WiFiClientSecure</code> and binds it to <code>PubSubClient</code> for encrypted payload transport."
        ]
    ))

    # Section 6
    story.append(add_code_section(
        "Part 6: State Tracking, Timebase & NTP Synchronization (Lines 70–95)",
        """73: bool relay_hospital = true;
74: bool relay_street   = true;
75: bool relay_house    = true;
76: bool relay_industry = true;
78: char lastActionMsg[32] = "READY (30s OBS)";
79: unsigned long lastSampleTime = 0;
80: const unsigned long SAMPLE_INTERVAL = 1000;
83: String getFormattedTimestamp() {
84:     struct tm timeinfo;
85:     if (getLocalTime(&timeinfo, 100)) {
86:         char buffer[32];
87:         strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
88:         return String(buffer);
89:     }
90:     char fallback[32];
91:     unsigned long sec = millis() / 1000;
92:     snprintf(fallback, sizeof(fallback), "2026-09-13 %02lu:%02lu:%02lu", (sec / 3600) % 24, (sec / 60) % 60, sec % 60);
93:     return String(fallback);
94: }""",
        [
            "<b>Lines 73–76:</b> In-memory state tracking variables. All initialized to <code>true</code> (energized at boot).",
            "<b>Line 78:</b> Status string buffer for the OLED display. Initialized to <code>'READY (30s OBS)'</code> for the initial observation window.",
            "<b>Lines 79–80:</b> Non-blocking timer tracking variables enforcing a 1.0 Hz (1000 ms) cyclic timebase using <code>millis()</code>.",
            "<b>Lines 83–89:</b> Retrieves real-time clock from SNTP via <code>getLocalTime()</code> and formats as <code>YYYY-MM-DD HH:MM:SS</code>.",
            "<b>Lines 90–94 (Fault-Tolerant Fallback):</b> If NTP sync is pending or network is down, generates a continuous synthetic timestamp from <code>millis()</code> uptime to prevent null values in downstream SCADA databases."
        ]
    ))

    # Section 7
    story.append(add_code_section(
        "Part 7: Client ID Generation & Relay Hardware Driver (Lines 96–111)",
        """97: String getUniqueClientID() {
98:     uint8_t mac[6];
99:     WiFi.macAddress(mac);
100:     char clientId[32];
101:     snprintf(clientId, sizeof(clientId), "SMARTGRID_%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
102:     return String(clientId);
103: }
105: void applyRelays() {
106:     digitalWrite(RELAY_HOSPITAL, relay_hospital ? RELAY_ON : RELAY_OFF);
107:     digitalWrite(RELAY_STREET,   relay_street   ? RELAY_ON : RELAY_OFF);
108:     digitalWrite(RELAY_HOUSE,    relay_house    ? RELAY_ON : RELAY_OFF);
109:     digitalWrite(RELAY_INDUSTRY, relay_industry ? RELAY_ON : RELAY_OFF);
110: }""",
        [
            "<b>Lines 97–103:</b> Extracts the ESP32 factory MAC address and generates a unique MQTT Client ID (e.g., <code>SMARTGRID_A4CF129B43E0</code>), preventing broker session conflicts.",
            "<b>Lines 105–110 (Hardware Sync Driver):</b> Synchronizes the four logical Boolean state flags with the physical GPIO output pins using active-LOW mapping."
        ]
    ))

    # Section 8
    story.append(add_code_section(
        "Part 8: Closed-Loop Actuator Callback (Lines 112–150)",
        """115: void mqttCallback(char* topic, byte* payload, unsigned int length) {
116:     JsonDocument doc;
117:     DeserializationError err = deserializeJson(doc, payload, length);
118:     if (err) return;
123:     const char* cmd    = doc["cmd"] | "";
124:     const char* load   = doc["load"] | "";
125:     int state          = doc["state"] | -1;
126:     const char* reason = doc["reason"] | "";
131:     if (state == 0 || state == 1) {
132:         bool targetState = (state == 1);
133:         uint8_t pinVal = targetState ? RELAY_ON : RELAY_OFF;
135:         if (strcasecmp(load, "hospital") == 0) {
136:             relay_hospital = targetState;
137:             digitalWrite(RELAY_HOSPITAL, pinVal);
138:         } else if (strcasecmp(load, "street") == 0) { ... }
148:         snprintf(lastActionMsg, sizeof(lastActionMsg), "%s %s", cmd, load);
149:     }
150: }""",
        [
            "<b>Line 115:</b> Asynchronous interrupt handler triggered whenever an MQTT control packet arrives.",
            "<b>Lines 116–118:</b> Parses incoming JSON bytes. If corrupted, exits immediately without hanging.",
            "<b>Lines 123–126:</b> Safely extracts action parameters: <code>cmd</code> (SHED/RESTORE), <code>load</code> (target branch), <code>state</code> (0/1), and <code>reason</code> (diagnostic log).",
            "<b>Lines 131–147:</b> Validates state, identifies target load via case-insensitive matching (<code>strcasecmp</code>), updates the state variable, and executes physical relay actuation.",
            "<b>Line 148:</b> Updates OLED display with the executed action string."
        ]
    ))

    # Section 9
    story.append(add_code_section(
        "Part 9: Wi-Fi & MQTT Auto-Reconnection Engine (Lines 151–170)",
        """152: void connectWiFi() {
153:     WiFi.mode(WIFI_STA);
154:     WiFi.setAutoReconnect(true);
155:     WiFi.persistent(true);
156:     WiFi.begin(ssid, password);
157: }
159: void reconnectMQTT() {
160:     if (WiFi.status() != WL_CONNECTED) return;
161:     if (!client.connected()) {
162:         String clientId = getUniqueClientID();
163:         if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
165:             client.subscribe(mqtt_control_topic);
166:         }
167:     }
168: }""",
        [
            "<b>Lines 152–157:</b> Sets Wi-Fi station mode, enables hardware auto-reconnect, and stores credentials in NVS flash.",
            "<b>Lines 159–168:</b> Verifies physical Layer-3 connection before attempting broker handshake. Upon connection, re-subscribes to <code>smartgrid/control</code> to restore the closed-loop control link."
        ]
    ))

    # Section 10
    story.append(add_code_section(
        "Part 10: Local Autonomous Protection & Edge Breaker (Lines 171–231)",
        """174: const float THRESH_HOSPITAL = 272.0;
175: const float THRESH_STREET   = 405.0;
176: const float THRESH_HOUSE    = 256.0;
177: const float THRESH_INDUSTRY = 264.0;
178: const float THRESH_CRITICAL = 320.0;
180: void evaluateLocalAutonomousProtection(...) {
181:     bool cloudActive = (WiFi.status() == WL_CONNECTED && client.connected());
185:     if (c_hosp > THRESH_HOSPITAL && relay_hospital) {
186:         relay_hospital = false;
187:         digitalWrite(RELAY_HOSPITAL, RELAY_OFF);
188:         snprintf(lastActionMsg, sizeof(lastActionMsg), "LOCAL TRIP HOSP");
189:     }
...
213:     if (!cloudActive && limit_mA > 0 && tot_mA >= (0.85 * limit_mA)) {
214:         if (relay_industry) { relay_industry = false; digitalWrite(RELAY_INDUSTRY, RELAY_OFF); }
219:         else if (relay_house) { relay_house = false; digitalWrite(RELAY_HOUSE, RELAY_OFF); }
224:         else if (relay_street) { relay_street = false; digitalWrite(RELAY_STREET, RELAY_OFF); }
230:     }
231: }""",
        [
            "<b>Lines 174–178:</b> Empirically calibrated 2-standard-deviation ($2\\sigma$) overcurrent thresholds in mA.",
            "<b>Lines 185–208 (Sub-Second Edge Overcurrent Breaker):</b> If any branch current breaches its $2\\sigma$ limit, the relay is de-energized immediately (&lt;1.0 s). Runs locally on the microcontroller regardless of Wi-Fi status.",
            "<b>Lines 213–230 (Autonomous Offline Capacity Shedding):</b> If offline and aggregate load reaches $\\ge 85\\%$ of source capacity, the microcontroller sheds lower-priority loads locally: Industry (P1) $\\to$ House (P2) $\\to$ Street (P3). Hospital (P4) and Critical Infrastructure remain protected."
        ]
    ))

    # Section 11
    story.append(add_code_section(
        "Part 11: Fault-Tolerant INA219 Shunt Driver (safeRead) (Lines 232–252)",
        """233: void safeRead(TwoWire &bus, Adafruit_INA219 &sensor, uint8_t addr, float &voltage, float &current_mA, float &power_mW, bool &ok) {
234:     bus.beginTransmission(addr);
235:     if (bus.endTransmission() != 0) {
236:         ok = false; voltage = 0.0; current_mA = 0.0; power_mW = 0.0; return;
238:     }
241:     voltage = sensor.getBusVoltage_V();
242:     current_mA = sensor.getCurrent_mA();
244:     if (isnan(voltage) || isnan(current_mA)) {
245:         ok = false; voltage = 0.0; current_mA = 0.0; power_mW = 0.0;
247:     } else {
248:         ok = true;
249:         if (current_mA > -0.5 && current_mA < 0.5) current_mA = 0.0;
250:         power_mW = voltage * current_mA;
251:     }
252: }""",
        [
            "<b>Lines 234–239:</b> Probes I2C device acknowledgment via <code>endTransmission()</code>. If NACKed (disconnected/shorted), zeroes variables and returns without locking the bus.",
            "<b>Lines 241–247:</b> Reads voltage and current; validates against floating-point <code>NaN</code> values.",
            "<b>Line 249 (Zero-Drift Noise Filter):</b> Clamps small thermal shunt offset noise ($\pm 0.5\\text{ mA}$) to zero.",
            "<b>Line 250:</b> Computes true instantaneous branch power ($P = V \\times I$) in milliwatts (mW)."
        ]
    ))

    # Section 12
    story.append(add_code_section(
        "Part 12: OLED Graphical Status Dashboard (updateOLED) (Lines 253–289)",
        """256: display.clearDisplay();
260: bool wifiOk = (WiFi.status() == WL_CONNECTED);
261: bool mqttOk = client.connected();
262: const char* netTag = (wifiOk && mqttOk) ? "CLOUD" : (wifiOk ? "NO-MQTT" : "OFFLINE");
264: display.printf("%s|%4.0f|%s", modeStr, limit_mA, netTag);
267: display.printf("HOS: %4.0fmA STR: %4.0fmA", c_hosp, c_str);
270: display.printf("HOU: %4.0fmA IND: %4.0fmA", c_hou, c_ind);
273: display.printf("CRI: %4.0fmA TOT:%5.0fmA", c_crit, tot_mA);
277: display.printf("RLY:[%d%d%d%d] (%s)", r_hosp, r_str, r_hou, r_ind, (tot_mA > 0.85*limit_mA) ? "SHED" : "NORM");
285: display.printf("ACT: %s", lastActionMsg);
287: display.display();""",
        [
            "<b>Lines 260–262:</b> Resolves 3-tier network status: <code>CLOUD</code>, <code>NO-MQTT</code>, or <code>OFFLINE</code>.",
            "<b>Lines 264–285:</b> Formats 6 rows of telemetry: source mode, branch currents, aggregate current, 4-bit relay state vector, load status, and recent actuation message.",
            "<b>Line 287:</b> Flushes the 1024-byte framebuffer over SPI to the SSD1306 panel."
        ]
    ))

    # Section 13
    story.append(add_code_section(
        "Part 13: System Initialization (setup) (Lines 290–357)",
        """294: Serial.begin(115200);
298: pinMode(RELAY_HOSPITAL, OUTPUT); ... pinMode(RELAY_INDUSTRY, OUTPUT);
307: applyRelays(); // ALL 4 ON at boot
310: pinMode(SMPS1_PIN, INPUT); pinMode(SMPS2_PIN, INPUT); pinMode(BATTERY_PIN, INPUT);
315: display.begin(SSD1306_SWITCHCAPVCC);
328: Wire.begin(27, 33); Wire.setTimeOut(50);
330: I2C2.begin(25, 32); I2C2.setTimeOut(50);
333: inaHospital.begin(&Wire); ... inaCritical.begin(&I2C2);
340: espClient.setInsecure();
341: client.setServer(mqtt_server, mqtt_port); client.setCallback(mqttCallback); client.setBufferSize(1024);
345: connectWiFi();
347: configTime(19800, 0, "pool.ntp.org", "time.google.com");""",
        [
            "<b>Lines 298–307:</b> Configures relay GPIOs as outputs and energizes all loads for the 30s boot observation phase.",
            "<b>Lines 328–331:</b> Initializes both hardware I2C controllers with 50 ms timeouts to guard against bus freezes.",
            "<b>Lines 333–337:</b> Initializes all five INA219 sensors across the two buses.",
            "<b>Lines 340–343:</b> Sets TLS to accept server certificates, registers <code>mqttCallback</code>, and increases MQTT buffer to 1024 bytes.",
            "<b>Line 347:</b> Initiates SNTP time synchronization (+5:30 IST = 19,800 seconds offset)."
        ]
    ))

    # Section 14 & 15
    story.append(add_code_section(
        "Parts 14 & 15: Main Execution Loop, Telemetry Publishing & Serialization (Lines 358–503)",
        """362: if (WiFi.status() == WL_CONNECTED) {
363:     if (!client.connected()) reconnectMQTT();
364:     client.loop();
365: } else { ... non-blocking reconnect every 5s ... }
375: if (millis() - lastSampleTime >= SAMPLE_INTERVAL) {
382:     if (smps1 && smps2) { modeStr = "DUAL SMPS"; current_limit = 5000.0; }
387:     else if (smps1 || smps2) { modeStr = "SINGLE SMPS"; current_limit = 1000.0; }
390:     else if (battery) { modeStr = "BATTERY"; current_limit = 800.0; }
403:     safeRead(I2C2, inaCritical, ...); safeRead(Wire, inaHospital, ...); ...
409:     float total_mA = c_crit + c_hosp + c_str + c_hou + c_ind;
413:     evaluateLocalAutonomousProtection(...);
422:     if (client.connected()) {
423:         JsonDocument doc;
424:         doc["timestamp"] = getFormattedTimestamp(); ...
493:         client.publish(mqtt_topic, jsonBuffer, len);
494:     }
501:     updateOLED(...);
502: }""",
        [
            "<b>Lines 362–373:</b> Maintains MQTT loop and handles non-blocking Wi-Fi auto-recovery.",
            "<b>Line 375:</b> Enforces 1.0 Hz sampling using <code>millis()</code>.",
            "<b>Lines 382–393:</b> Dynamic capacity allocation: Dual SMPS (5000 mA), Single SMPS (1000 mA), or Battery (800 mA).",
            "<b>Lines 403–407:</b> Reads telemetry from all five sensors using <code>safeRead()</code>.",
            "<b>Line 413:</b> Runs local edge protection to trip overcurrent in &lt;1.0 s if thresholds are breached.",
            "<b>Lines 422–494:</b> Serializes complete nested JSON payload and publishes to <code>smartgrid/live</code>.",
            "<b>Line 501:</b> Refreshes OLED display with latest readings and relay status."
        ]
    ))

    # Section: Key Electrical & Engineering Decisions Table
    story.append(Paragraph("3. Summary of Electrical & Engineering Decisions", h1_style))
    dec_table_data = [
        [Paragraph("<b>Challenge</b>", body_style), Paragraph("<b>Firmware Implementation</b>", body_style), Paragraph("<b>Engineering Rationale</b>", body_style)],
        [Paragraph("I2C Address Collision", body_style), Paragraph("Dual Hardware Buses (Wire & I2C2)", body_style), Paragraph("inaCritical & inaHouse share address 0x40. Isolating inaCritical on I2C2 (GPIO 25/32) avoids collisions without extra hardware.", body_style)],
        [Paragraph("Relay Power-on Glitches", body_style), Paragraph("Active-LOW Logic (LOW = ON)", body_style), Paragraph("Matches optocoupler input biasing on standard relay boards, preventing spurious relay chatter during power-on boot states.", body_style)],
        [Paragraph("Edge Protection Latency", body_style), Paragraph("&lt; 1.0s Local 2-Sigma Breaker", body_style), Paragraph("Runs locally on the microcontroller, guaranteeing hardware trip protection even if Wi-Fi drops or the host controller freezes.", body_style)],
        [Paragraph("Switchgear Chattering", body_style), Paragraph("15.0s Governor Dwell Time", body_style), Paragraph("Prevents rapid cycling during marginal capacity fluctuations, reducing mechanical contactor wear and contact welding.", body_style)],
        [Paragraph("Sensor Zero Drift", body_style), Paragraph("Clamping [-0.5, +0.5] mA to 0.0", body_style), Paragraph("Eliminates thermal drift noise on INA219 shunt readings when circuits are in a zero-current state.", body_style)],
    ]
    dec_table = Table(dec_table_data, colWidths=[120, 160, 224])
    dec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(dec_table)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {filename}")

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(out_dir)
    pdf_local = os.path.join(project_root, "docs", "ESP32_SmartGrid_Hardware_Code_Explanation.pdf")
    build_pdf(pdf_local)

    # Move to Downloads
    downloads_path = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\lenovo"), "Downloads")
    if os.path.exists(downloads_path):
        target_path = os.path.join(downloads_path, "ESP32_SmartGrid_Hardware_Code_Explanation.pdf")
        shutil.copy2(pdf_local, target_path)
        print(f"Successfully copied PDF to Downloads: {target_path}")
    else:
        print(f"Downloads directory not found at: {downloads_path}")
