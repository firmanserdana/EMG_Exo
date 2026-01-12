#include <WiFi.h>
#include <WiFiUdp.h>

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
bool wifiConnected = false;
unsigned long lastWifiAttempt = 0;
int lastStableButtonState = BUTTON_ACTIVE_LOW ? HIGH : LOW;
int lastRawButtonReading = lastStableButtonState;
unsigned long lastDebounceTime = 0;

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

    bool ledState = wifiConnected;
    digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
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
    
    WiFi.mode(WIFI_STA);
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
    // Priority 1: Send UDP (faster)
    if (WIFI_BRIDGE_ENABLED && wifiConnected)
    {
        udp.beginPacket(GLOVE_HOST_IP, GLOVE_UDP_PORT);
        udp.print(command);
        udp.write('\n');
        udp.endPacket();
    }

    // Priority 2: Send Serial
    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.print(command);
        BRIDGE_SERIAL.print('\n');
        BRIDGE_SERIAL.flush(); // Ensure immediate transmission
    }

    logLine("[BRIDGE] Sent command -> " + String(command));
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
    
    // Priority 2: WiFi connection maintenance
    ensureWifi();
    
    // Priority 3: LED status update (lowest priority)
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
    }
    
    // No delay() - keep loop responsive
}
