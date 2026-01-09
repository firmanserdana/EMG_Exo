
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
const uint32_t WIFI_RECONNECT_INTERVAL_MS = 1000; // 减少到1秒，原来是5秒

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
const uint32_t BUTTON_DEBOUNCE_MS = 30; // 减少到30ms，原来是40ms

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
    
    // 等待连接最多3秒
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
    // 优先发送UDP（更快）
    if (WIFI_BRIDGE_ENABLED && wifiConnected)
    {
        udp.beginPacket(GLOVE_HOST_IP, GLOVE_UDP_PORT);
        udp.print(command);
        udp.write('\n');
        udp.endPacket();
    }

    // 然后发送Serial
    if (SERIAL_BRIDGE_ENABLED)
    {
        BRIDGE_SERIAL.print(command);
        BRIDGE_SERIAL.print('\n');
        BRIDGE_SERIAL.flush(); // 确保立即发送
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
    logLine("\n=== Button Bridge (Optimized) ===");

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
        // WiFi配置优化
        logLine("[BRIDGE] Configuring WiFi...");
        WiFi.persistent(false); // 不保存WiFi配置到flash，加快连接
        WiFi.setAutoReconnect(true);
        
        logLine("[BRIDGE] Target SSID: " + String(WIFI_SSID));
        logLine("[BRIDGE] Target IP: " + GLOVE_HOST_IP.toString());
        logLine("[BRIDGE] Waiting 2 seconds for AP to be ready...");
        delay(2000); // 等待手套的AP启动完成
        
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
    // 优先级1: 按钮检测（最高优先级）
    pollButton();
    
    // 优先级2: WiFi连接维护（在按钮检测之后）
    ensureWifi();
    
    // 优先级3: LED状态更新（最低优先级）
    updateStatusLed();

    // 减少心跳日志频率，避免阻塞
    static unsigned long lastHeartbeat = 0;
    unsigned long now = millis();
    if (now - lastHeartbeat > 30000) // 改为30秒
    {
        lastHeartbeat = now;
        if (WIFI_BRIDGE_ENABLED)
        {
            logLine("[BRIDGE] Status - WiFi: " + wifiStatusToString(WiFi.status()) + 
                    ", Connected: " + String(wifiConnected ? "Yes" : "No"));
        }
    }
    
    // 不添加任何delay，保持loop最快响应
}
