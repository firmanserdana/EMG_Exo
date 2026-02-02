#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>

// FireBeetle ESP32 板载LED
#define LED_BUILTIN 2

// ======================================================
//                Button Bridge Configuration
// ======================================================
// WiFi link to the glove controller (ESP32_Glove AP by default)
const bool WIFI_BRIDGE_ENABLED = true;
const char *WIFI_SSID = "ESP32_Glove";
const char *WIFI_PASSWORD = "12345678";
const IPAddress GLOVE_HOST_IP(192, 168, 4, 1);
const uint16_t GLOVE_UDP_PORT = 4211;
const uint16_t LOCAL_UDP_PORT = 0; // 0 lets the stack pick a free port
const uint32_t WIFI_RECONNECT_INTERVAL_MS = 1000;

// Web GUI Configuration (Button Bridge acts as AP for phone access)
const bool WEB_GUI_ENABLED = true;
const char *AP_SSID = "ButtonBridge";
const char *AP_PASSWORD = "12345678";
const uint16_t WEB_SERVER_PORT = 80;

// Optional UART forwarding to the main ESP32
const bool SERIAL_BRIDGE_ENABLED = true;
HardwareSerial &BRIDGE_SERIAL = Serial1;
const int SERIAL_TX_PIN = 16; // FireBeetle D9 -> Glove RX
const int SERIAL_RX_PIN = 17; // FireBeetle D10 -> Glove TX (optional)
const uint32_t SERIAL_BAUD_RATE = 115200;

// Button wiring - FireBeetle ESP32 specific
const int BUTTON_PIN = 25;             // FireBeetle GPIO25 (D2引脚)
const bool BUTTON_ACTIVE_LOW = true;   // Button pulls pin LOW when pressed
const bool USE_INTERNAL_PULLUP = true; // Uses INPUT_PULLUP
const uint32_t BUTTON_DEBOUNCE_MS = 30;

// Status LED - FireBeetle onboard LED
const bool STATUS_LED_ENABLED = true;
const int STATUS_LED_PIN = LED_BUILTIN; // FireBeetle板载LED (GPIO2)

// Command behaviour
const bool SEND_PRESS_COMMAND = true; // Sends BTN:PRESS on falling edge
const bool SEND_ON_COMMAND = false;   // Sends BTN:ON on press
const bool SEND_OFF_COMMAND = false;  // Sends BTN:OFF on release
const char *PRESS_COMMAND = "BTN:PRESS";
const char *ON_COMMAND = "BTN:ON";
const char *OFF_COMMAND = "BTN:OFF";

// ======================================================
//                 Internal State Variables
// ======================================================
WiFiUDP udp;
WebServer webServer(WEB_SERVER_PORT);
bool wifiConnected = false;
unsigned long lastWifiAttempt = 0;
int lastStableButtonState = BUTTON_ACTIVE_LOW ? HIGH : LOW;
int lastRawButtonReading = lastStableButtonState;
unsigned long lastDebounceTime = 0;
unsigned long lastWebButtonPress = 0;
int webButtonPressCount = 0;

// ======================================================
//                     Web GUI HTML
// ======================================================
const char *WEB_GUI_HTML = R"rawliteral(
<!DOCTYPE HTML>
<html>
<head>
    <title>Button Bridge Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
        * { box-sizing: border-box; touch-action: manipulation; }
        html, body { 
            margin: 0; padding: 0; height: 100%; width: 100%;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            overflow: hidden;
        }
        .container {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 100%; padding: 20px;
        }
        h1 {
            color: #e94560; margin: 0 0 10px 0; font-size: 24px;
            text-shadow: 0 0 20px rgba(233,69,96,0.5);
        }
        .status {
            color: #94b4c1; font-size: 14px; margin-bottom: 20px;
            text-align: center; line-height: 1.5;
        }
        .status-dot {
            display: inline-block; width: 10px; height: 10px;
            border-radius: 50%; margin-right: 6px; vertical-align: middle;
        }
        .status-online { background: #00ff88; box-shadow: 0 0 10px #00ff88; }
        .status-offline { background: #ff4444; box-shadow: 0 0 10px #ff4444; }
        
        .big-button {
            width: 280px; height: 280px;
            border-radius: 50%;
            background: linear-gradient(145deg, #e94560, #c73b54);
            border: none;
            box-shadow: 
                0 15px 35px rgba(233,69,96,0.4),
                0 5px 15px rgba(0,0,0,0.3),
                inset 0 -8px 20px rgba(0,0,0,0.2),
                inset 0 8px 20px rgba(255,255,255,0.1);
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            flex-direction: column;
            transition: all 0.1s ease;
            -webkit-tap-highlight-color: transparent;
        }
        .big-button:active {
            transform: scale(0.95);
            box-shadow: 
                0 5px 15px rgba(233,69,96,0.3),
                0 2px 8px rgba(0,0,0,0.2),
                inset 0 4px 15px rgba(0,0,0,0.3);
        }
        .big-button .icon {
            font-size: 80px; color: white;
            text-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .big-button .text {
            font-size: 28px; color: white; font-weight: bold;
            margin-top: 10px; letter-spacing: 2px;
            text-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        
        .press-count {
            margin-top: 20px; color: #94b4c1; font-size: 16px;
        }
        .press-count span { color: #00ff88; font-weight: bold; font-size: 24px; }
        
        .feedback {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%) scale(0);
            background: rgba(0,255,136,0.9); color: #1a1a2e;
            padding: 20px 40px; border-radius: 10px;
            font-size: 24px; font-weight: bold;
            pointer-events: none; opacity: 0;
            transition: all 0.2s ease;
        }
        .feedback.show {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Button Bridge</h1>
        <div class="status">
            <div>
                <span class="status-dot" id="glove-status"></span>
                Glove: <span id="glove-text">Checking...</span>
            </div>
        </div>
        
        <button class="big-button" id="mainButton" ontouchstart="pressButton(event)" onmousedown="pressButton(event)">
            <span class="icon">👆</span>
            <span class="text">PRESS</span>
        </button>
        
        <div class="press-count">
            Presses: <span id="pressCount">0</span>
        </div>
    </div>
    
    <div class="feedback" id="feedback">SENT!</div>

    <script>
        let pressCount = 0;
        let lastPressTime = 0;
        const debounceMs = 200;
        
        // Audio context for button sound
        let audioCtx = null;
        function playBeep() {
            try {
                if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.frequency.value = 800;
                osc.type = 'sine';
                gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
                osc.start(audioCtx.currentTime);
                osc.stop(audioCtx.currentTime + 0.15);
            } catch(e) {}
        }
        
        function pressButton(e) {
            e.preventDefault();
            
            const now = Date.now();
            if (now - lastPressTime < debounceMs) return;
            lastPressTime = now;
            
            playBeep();
            
            fetch('/press')
                .then(response => response.json())
                .then(data => {
                    pressCount = data.count;
                    document.getElementById('pressCount').textContent = pressCount;
                    showFeedback();
                })
                .catch(err => {
                    pressCount++;
                    document.getElementById('pressCount').textContent = pressCount;
                    showFeedback();
                });
        }
        
        function showFeedback() {
            const fb = document.getElementById('feedback');
            fb.classList.add('show');
            setTimeout(() => fb.classList.remove('show'), 300);
        }
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const dot = document.getElementById('glove-status');
                    const text = document.getElementById('glove-text');
                    document.getElementById('pressCount').textContent = data.count;
                    
                    if (data.wifi_connected) {
                        dot.className = 'status-dot status-online';
                        text.textContent = 'Connected';
                    } else {
                        dot.className = 'status-dot status-offline';
                        text.textContent = 'Disconnected';
                    }
                })
                .catch(err => {
                    document.getElementById('glove-status').className = 'status-dot status-offline';
                    document.getElementById('glove-text').textContent = 'Error';
                });
        }
        
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
)rawliteral";

// ======================================================
//                         Helpers
// ======================================================
void logLine(const String &msg)
{
    Serial.println(msg);
}

String wifiStatusToString(wl_status_t status)
{
    switch (status)
    {
    case WL_IDLE_STATUS:
        return "Idle";
    case WL_NO_SSID_AVAIL:
        return "SSID not found";
    case WL_SCAN_COMPLETED:
        return "Scan complete";
    case WL_CONNECTED:
        return "Connected";
    case WL_CONNECT_FAILED:
        return "Connect failed";
    case WL_CONNECTION_LOST:
        return "Connection lost";
    case WL_DISCONNECTED:
        return "Disconnected";
    default:
        return "Unknown";
    }
}

void updateStatusLed()
{
    if (!STATUS_LED_ENABLED)
    {
        return;
    }

    // Blink pattern: solid = connected, slow blink = AP only, fast blink = connecting
    static unsigned long lastBlink = 0;
    static bool ledState = false;
    unsigned long now = millis();

    if (wifiConnected)
    {
        // Solid on when connected to glove
        digitalWrite(STATUS_LED_PIN, HIGH);
    }
    else if (WEB_GUI_ENABLED)
    {
        // Slow blink when AP is active but not connected to glove
        if (now - lastBlink > 1000)
        {
            lastBlink = now;
            ledState = !ledState;
            digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
        }
    }
    else
    {
        digitalWrite(STATUS_LED_PIN, LOW);
    }
}

void ensureWifi()
{
    if (!WIFI_BRIDGE_ENABLED)
    {
        return;
    }

    wl_status_t status = WiFi.status();

    if (status == WL_CONNECTED)
    {
        if (!wifiConnected)
        {
            wifiConnected = true;
            logLine("[BRIDGE] WiFi connected: " + WiFi.localIP().toString());
            if (!udp.begin(LOCAL_UDP_PORT))
            {
                logLine("[BRIDGE] Failed to open UDP socket");
            }
            else
            {
                logLine("[BRIDGE] UDP socket opened successfully");
            }
        }
        return;
    }

    // Not connected - throttle reconnection attempts
    unsigned long now = millis();
    if (now - lastWifiAttempt < WIFI_RECONNECT_INTERVAL_MS)
    {
        return;
    }
    lastWifiAttempt = now;

    if (wifiConnected)
    {
        logLine("[BRIDGE] WiFi connection lost, status: " + wifiStatusToString(status));
        wifiConnected = false;
    }

    logLine("[BRIDGE] Attempting to connect to WiFi SSID: " + String(WIFI_SSID));
    logLine("[BRIDGE] Current status: " + wifiStatusToString(status));

    // Keep AP+STA mode if web GUI is enabled, otherwise STA only
    if (WEB_GUI_ENABLED)
    {
        WiFi.mode(WIFI_AP_STA);
        WiFi.softAP(AP_SSID, AP_PASSWORD); // Re-ensure AP is active
    }
    else
    {
        WiFi.mode(WIFI_STA);
    }
    delay(100);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    // Wait for connection up to 3 seconds
    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 3000)
    {
        delay(100);
        logLine("[BRIDGE] Connecting... status: " + wifiStatusToString(WiFi.status()));
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        wifiConnected = true;
        logLine("[BRIDGE] WiFi connected successfully: " + WiFi.localIP().toString());
    }
    else
    {
        logLine("[BRIDGE] WiFi connection failed: " + wifiStatusToString(WiFi.status()));
    }
}

void sendCommand(const char *command)
{
    bool udpSent = false;
    bool serialSent = false;

    // Priority 1: Send UDP (faster)
    if (WIFI_BRIDGE_ENABLED && wifiConnected)
    {
        udp.beginPacket(GLOVE_HOST_IP, GLOVE_UDP_PORT);
        udp.print(command);
        udp.write('\n');
        if (udp.endPacket())
        {
            udpSent = true;
        }
    }

    // Priority 2: Send Serial (always try if enabled)
    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.print(command);
        BRIDGE_SERIAL.print('\n');
        BRIDGE_SERIAL.flush(); // Ensure immediate transmission
        serialSent = true;
    }

    // Log what was sent
    String status = "[BRIDGE] Sent: " + String(command) + " via ";
    if (udpSent)
        status += "UDP ";
    if (serialSent)
        status += "Serial ";
    if (!udpSent && !serialSent)
        status += "NOTHING (no connection!)";
    logLine(status);
}

// Web button press handler
void handleWebButtonPress()
{
    unsigned long now = millis();
    if (now - lastWebButtonPress >= BUTTON_DEBOUNCE_MS)
    {
        lastWebButtonPress = now;
        webButtonPressCount++;
        sendCommand(PRESS_COMMAND);
    }

    String response = "{\"status\":\"ok\",\"count\":" + String(webButtonPressCount) + "}";
    webServer.send(200, "application/json", response);
}

void handleWebStatus()
{
    String json = "{";
    json += "\"wifi_connected\":" + String(wifiConnected ? "true" : "false");
    json += ",\"count\":" + String(webButtonPressCount);
    json += ",\"uptime\":" + String(millis() / 1000);
    json += "}";
    webServer.send(200, "application/json", json);
}

void handleWebRoot()
{
    webServer.send(200, "text/html", WEB_GUI_HTML);
}

void initWebServer()
{
    if (!WEB_GUI_ENABLED)
    {
        return;
    }

    webServer.on("/", handleWebRoot);
    webServer.on("/press", handleWebButtonPress);
    webServer.on("/status", handleWebStatus);
    webServer.begin();

    logLine("[BRIDGE] Web server started on port " + String(WEB_SERVER_PORT));
}

void handleButtonChange(int stableState)
{
    bool pressed = BUTTON_ACTIVE_LOW ? (stableState == LOW) : (stableState == HIGH);

    if (pressed)
    {
        if (SEND_PRESS_COMMAND)
        {
            sendCommand(PRESS_COMMAND);
        }
        if (SEND_ON_COMMAND)
        {
            sendCommand(ON_COMMAND);
        }
    }
    else
    {
        if (SEND_OFF_COMMAND)
        {
            sendCommand(OFF_COMMAND);
        }
    }
}

void pollButton()
{
    int rawReading = digitalRead(BUTTON_PIN);
    unsigned long now = millis();

    if (rawReading != lastRawButtonReading)
    {
        lastDebounceTime = now;
        lastRawButtonReading = rawReading;
    }

    if ((now - lastDebounceTime) >= BUTTON_DEBOUNCE_MS && rawReading != lastStableButtonState)
    {
        lastStableButtonState = rawReading;
        handleButtonChange(lastStableButtonState);
    }
}

// ======================================================
//                        Arduino API
// ======================================================
void setup()
{
    Serial.begin(115200);
    delay(500);
    logLine("\n=== Button Bridge for FireBeetle ESP32 ===");
    logLine("[BRIDGE] Board: DFRobot FireBeetle ESP32");
    logLine("[BRIDGE] Button Pin: GPIO25 (D2)");

    // Initialize button pin with internal pullup
    if (USE_INTERNAL_PULLUP)
    {
        pinMode(BUTTON_PIN, BUTTON_ACTIVE_LOW ? INPUT_PULLUP : INPUT_PULLDOWN);
        logLine("[BRIDGE] Button configured with internal pullup on GPIO25");
    }
    else
    {
        pinMode(BUTTON_PIN, INPUT);
    }

    // Initialize status LED
    if (STATUS_LED_ENABLED)
    {
        pinMode(STATUS_LED_PIN, OUTPUT);
        digitalWrite(STATUS_LED_PIN, LOW);
        logLine("[BRIDGE] Status LED enabled on GPIO2 (onboard LED)");
    }

    // Initialize serial bridge if enabled
    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.begin(SERIAL_BAUD_RATE, SERIAL_8N1, SERIAL_RX_PIN, SERIAL_TX_PIN);
        logLine("[BRIDGE] Serial forwarding enabled @" + String(SERIAL_BAUD_RATE));
        logLine("[BRIDGE] TX: GPIO16 (D9), RX: GPIO17 (D10)");
    }
    else
    {
        logLine("[BRIDGE] Serial forwarding disabled");
    }

    // Initialize WiFi if enabled
    if (WIFI_BRIDGE_ENABLED)
    {
        logLine("[BRIDGE] Configuring WiFi...");
        WiFi.persistent(false); // Don't save WiFi config to flash
        WiFi.setAutoReconnect(true);

        logLine("[BRIDGE] Target SSID: " + String(WIFI_SSID));
        logLine("[BRIDGE] Target IP: " + GLOVE_HOST_IP.toString());
        logLine("[BRIDGE] Waiting 2 seconds for AP to be ready...");
        delay(2000); // Wait for glove AP to start

        ensureWifi();
    }
    else
    {
        logLine("[BRIDGE] WiFi forwarding disabled");
    }

    logLine("[BRIDGE] Setup complete. Ready for button events...");
    logLine("[BRIDGE] Press the button to test!");
}

void loop()
{
    // Priority 1: Button detection (highest priority)
    pollButton();

    // Priority 2: Web server handling
    if (WEB_GUI_ENABLED)
    {
        webServer.handleClient();
    }

    // Priority 3: WiFi connection maintenance
    ensureWifi();

    // Priority 4: LED status update (lowest priority)
    updateStatusLed();

    // Reduce heartbeat log frequency to avoid blocking
    static unsigned long lastHeartbeat = 0;
    unsigned long now = millis();
    if (now - lastHeartbeat > 30000) // 30 seconds
    {
        lastHeartbeat = now;
        if (WIFI_BRIDGE_ENABLED)
        {
            logLine("[BRIDGE] Status - WiFi: " + wifiStatusToString(WiFi.status()) +
                    ", Connected: " + String(wifiConnected ? "Yes" : "No"));
        }
        if (WEB_GUI_ENABLED)
        {
            logLine("[BRIDGE] AP clients: " + String(WiFi.softAPgetStationNum()) +
                    ", Web presses: " + String(webButtonPressCount));
        }
    }

    // No delay() - keep loop responsive
}
