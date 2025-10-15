#include <WiFi.h>
#include <WiFiUdp.h>

#ifndef LED_BUILTIN
#define LED_BUILTIN 2 // default onboard LED for most ESP32 dev kits
#endif

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
const uint32_t WIFI_RECONNECT_INTERVAL_MS = 5000;

// Optional UART forwarding to the main ESP32
const bool SERIAL_BRIDGE_ENABLED = true;
HardwareSerial &BRIDGE_SERIAL = Serial1;
const int SERIAL_TX_PIN = 17; // Bridge TX -> ESP32 RX2 (GPIO35)
const int SERIAL_RX_PIN = 16; // Optional, only if acknowledgements are required
const uint32_t SERIAL_BAUD_RATE = 115200;

// Button wiring
const int BUTTON_PIN = 12;             // Adjust to suit your bridge board
const bool BUTTON_ACTIVE_LOW = true;   // Board pulls the pin LOW when pressed
const bool USE_INTERNAL_PULLUP = true; // Uses INPUT_PULLUP if true
const uint32_t BUTTON_DEBOUNCE_MS = 40;

// Status LED (optional)
const bool STATUS_LED_ENABLED = true;
const int STATUS_LED_PIN = LED_BUILTIN;

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

    if (WiFi.status() == WL_CONNECTED)
    {
        if (!wifiConnected)
        {
            wifiConnected = true;
            logLine("[BRIDGE] WiFi connected: " + WiFi.localIP().toString());
            if (!udp.begin(LOCAL_UDP_PORT))
            {
                logLine("[BRIDGE] Failed to open UDP socket");
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
        logLine("[BRIDGE] WiFi connection lost");
        wifiConnected = false;
    }

    logLine("[BRIDGE] Connecting to WiFi SSID " + String(WIFI_SSID) + "...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void sendCommand(const char *command)
{
    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.print(command);
        BRIDGE_SERIAL.print('\n');
    }

    if (WIFI_BRIDGE_ENABLED && wifiConnected)
    {
        udp.beginPacket(GLOVE_HOST_IP, GLOVE_UDP_PORT);
        udp.print(command);
        udp.write('\n');
        udp.endPacket();
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
    delay(200);
    logLine("\n=== Button Bridge ===");

    if (USE_INTERNAL_PULLUP)
    {
        pinMode(BUTTON_PIN, BUTTON_ACTIVE_LOW ? INPUT_PULLUP : INPUT_PULLDOWN);
    }
    else
    {
        pinMode(BUTTON_PIN, INPUT);
    }

    if (STATUS_LED_ENABLED)
    {
        pinMode(STATUS_LED_PIN, OUTPUT);
        digitalWrite(STATUS_LED_PIN, LOW);
    }

    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.begin(SERIAL_BAUD_RATE, SERIAL_8N1, SERIAL_RX_PIN, SERIAL_TX_PIN);
        logLine("[BRIDGE] Serial forwarding enabled @" + String(SERIAL_BAUD_RATE));
    }
    else
    {
        logLine("[BRIDGE] Serial forwarding disabled");
    }

    if (WIFI_BRIDGE_ENABLED)
    {
        ensureWifi();
    }
    else
    {
        logLine("[BRIDGE] WiFi forwarding disabled");
    }

    logLine("[BRIDGE] Ready. Waiting for button events...");
}

void loop()
{
    ensureWifi();
    pollButton();
    updateStatusLed();

    static unsigned long lastHeartbeat = 0;
    unsigned long now = millis();
    if (now - lastHeartbeat > 5000)
    {
        lastHeartbeat = now;
        if (WIFI_BRIDGE_ENABLED)
        {
            logLine("[BRIDGE] WiFi status: " + wifiStatusToString(WiFi.status()));
        }
    }
}
