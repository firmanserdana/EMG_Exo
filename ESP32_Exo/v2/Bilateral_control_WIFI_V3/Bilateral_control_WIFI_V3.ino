#include <Adafruit_MCP4728.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>
#include <WebServer.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include "config.h"

// ==================== Configuration ====================
const char *ap_ssid = "ESP32_Glove";
const char *ap_password = "12345678";
const char *sta_ssid = WIFI_STA_SSID;
const char *sta_password = WIFI_STA_PASSWORD;
const int tcp_port = 4210;

// ==================== Hardware Configuration ====================
const int flexion_pins[5] = {13, 14, 12, 27, 15};
const int extension_pins[5] = {17, 5, 18, 19, 15};
const int pinching_pins[5] = {4, 4, 4, 4, 4};
const int abduction_pin = 15;
const int adduction_pin = 16;
const int emergency_pin = 4;

const bool button_bridge_serial_enabled = true;
const int button_serial_rx_pin = 35;
const int button_serial_tx_pin = 4;
const unsigned long button_bridge_activity_timeout = 10000;

const bool button_bridge_wifi_enabled = true;
const unsigned int button_udp_port = 4211;

const int sda_pin = 21;
const int scl_pin = 22;

// ==================== Global Variables ====================
enum ControlMode { WEB_MODE, TCP_MODE, BUTTON_MODE };
ControlMode control_mode = WEB_MODE;

enum ControlModeLock { AUTO_MODE, FORCE_WEB_MODE, FORCE_TCP_MODE, FORCE_BUTTON_MODE };
ControlModeLock mode_lock = AUTO_MODE;

int gesture = 0;
int pressure[2] = {50, 50};
int speed = 0;
String finger_states = "000000";

const char *GESTURE_TO_FINGER_STATES_MAP[] = {
    "000000", "111110", "222222", "011110", "111110",
    "100000", "010000", "001110", "121110"
};
const int NUM_GESTURES = sizeof(GESTURE_TO_FINGER_STATES_MAP) / sizeof(GESTURE_TO_FINGER_STATES_MAP[0]);

WebServer server(80);
WiFiServer tcpServer(tcp_port);
WiFiClient tcpClient;
Adafruit_MCP4728 dac;
bool dac_available = false;

bool tcp_connected = false;
bool tcp_server_started = false;
unsigned long last_tcp_command = 0;
const unsigned long tcp_timeout = 20000;
char tcp_command_buffer[256];
int tcp_buffer_idx = 0;

bool status_changed = true;

unsigned long last_button_press = 0;
const unsigned long button_debounce_delay = 150; // 减少到150ms
int button_gestures[3] = {1, 2, 0};
int button_cycle_mode = 2;
int button_cycle_position = 0;

HardwareSerial &button_serial = Serial2;
WiFiUDP button_udp;
char button_serial_buffer[64];
size_t button_serial_buffer_idx = 0;
bool button_udp_initialized = false;
unsigned long last_button_bridge_serial_activity = 0;
unsigned long last_button_bridge_wifi_activity = 0;
unsigned long last_button_bridge_activity = 0;
String last_button_bridge_source = "none";

// ==================== 新增：命令队列防止堵塞 ====================
struct Command {
    enum Type { NONE, BUTTON, TCP, WEB } type;
    String data;
    unsigned long timestamp;
};

const int COMMAND_QUEUE_SIZE = 10;
Command commandQueue[COMMAND_QUEUE_SIZE];
int queueHead = 0;
int queueTail = 0;
int queueCount = 0;

bool enqueueCommand(Command::Type type, const String& data) {
    if (queueCount >= COMMAND_QUEUE_SIZE) {
        Serial.println("WARNING: Command queue full!");
        return false;
    }
    commandQueue[queueTail].type = type;
    commandQueue[queueTail].data = data;
    commandQueue[queueTail].timestamp = millis();
    queueTail = (queueTail + 1) % COMMAND_QUEUE_SIZE;
    queueCount++;
    return true;
}

bool dequeueCommand(Command& cmd) {
    if (queueCount == 0) {
        return false;
    }
    cmd = commandQueue[queueHead];
    queueHead = (queueHead + 1) % COMMAND_QUEUE_SIZE;
    queueCount--;
    return true;
}

// ==================== HTML Page (保持不变) ====================
const char *html_page = R"rawliteral(
<!DOCTYPE HTML>
<html>
<head>
    <title>ESP32 Glove Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; text-align: center; background: #f0f0f0; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 20px; font-size: 24px; }
        .section { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }
        .section h3 { margin: 0 0 15px 0; color: #666; font-size: 18px; }
        .button-group { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 10px 0; }
        button { padding: 10px 16px; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; transition: all 0.3s; }
        .btn-primary { background: #007bff; color: white; }
        .btn-primary:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-secondary:hover { background: #545b62; }
        .btn-danger { background: #dc3545; color: white; }
        .control-row { display: flex; align-items: center; justify-content: space-between; margin: 8px 0; }
        input[type="number"] { width: 80px; padding: 6px; border: 1px solid #ddd; border-radius: 4px; text-align: center; }
        input[type="text"] { padding: 6px; border: 1px solid #ddd; border-radius: 4px; text-align: center; }
        select { padding: 6px; border: 1px solid #ddd; border-radius: 4px; min-width: 140px; }
        .status { margin: 10px 0; padding: 12px; background: #f8f9fa; border-radius: 5px; font-family: monospace; font-size: 12px; border-left: 4px solid #007bff; }
        .mode-indicator { padding: 6px 14px; border-radius: 20px; color: white; font-weight: bold; display: inline-block; font-size: 13px; }
        .mode-web { background: #28a745; }
        .mode-tcp { background: #17a2b8; }
        .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }
        .status-item { background: #e9ecef; padding: 8px; border-radius: 5px; font-size: 13px; }
        .status-value { font-weight: bold; color: #007bff; font-size: 16px; }
        .connection-status { display: flex; align-items: center; gap: 8px; margin: 5px 0; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; }
        .status-online { background: #28a745; }
        .status-offline { background: #dc3545; }
        .realtime-display { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin: 15px 0; }
        .gesture-display { font-size: 20px; font-weight: bold; margin: 8px 0; }
        .btn-config { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 10px 0; }
        .pos-card { background: #f8f9fa; padding: 10px; border-radius: 6px; border: 2px solid #ddd; }
        .pos-card.active { border-color: #007bff; background: #e7f3ff; }
        .pos-label { font-weight: bold; color: #666; margin-bottom: 8px; font-size: 13px; }
        .pos-current { text-align: center; margin: 10px 0; font-size: 15px; }
        .pos-current span { font-weight: bold; color: #007bff; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ESP32 Glove Control (Optimized)</h1>
        
        <div class="section">
            <h3>System Status</h3>
            <div id="mode-status" class="mode-indicator mode-web">Web Mode</div>
            <div class="status">
                <div class="connection-status">
                    <span>AP:</span>
                    <div class="status-dot status-online"></div>
                    <span>192.168.4.1</span>
                </div>
                <div class="connection-status">
                    <span>STA:</span>
                    <div id="sta-dot" class="status-dot status-offline"></div>
                    <span id="sta-status">Connecting...</span>
                </div>
                <div class="connection-status">
                    <span>TCP:</span>
                    <div id="tcp-dot" class="status-dot status-offline"></div>
                    <span id="tcp-status">Waiting...</span>
                </div>
                <div class="connection-status">
                    <span>Button Bridge:</span>
                    <div id="button-bridge-dot" class="status-dot status-offline"></div>
                    <span id="button-bridge-status">Waiting...</span>
                </div>
            </div>
        </div>

        <div class="realtime-display">
            <h3 style="margin-top: 0;">Current State</h3>
            <div class="gesture-display">Gesture: <span id="current-gesture">Relax</span></div>
            <div class="status-grid">
                <div class="status-item">
                    <div>Flex Pressure</div>
                    <div class="status-value"><span id="current-flex">50</span>%</div>
                </div>
                <div class="status-item">
                    <div>Ext Pressure</div>
                    <div class="status-value"><span id="current-ext">50</span>%</div>
                </div>
                <div class="status-item">
                    <div>Speed Level</div>
                    <div class="status-value"><span id="current-speed">1</span>/4</div>
                </div>
                <div class="status-item">
                    <div>Finger States</div>
                    <div class="status-value"><span id="current-fingers">000000</span></div>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>Control Mode</h3>
            <div class="status-grid" style="margin-bottom: 10px;">
                <div class="status-item">
                    <div>Mode</div>
                    <div class="status-value"><span id="current-mode">WEB</span></div>
                </div>
                <div class="status-item">
                    <div>Lock</div>
                    <div class="status-value"><span id="mode-lock-status">AUTO</span></div>
                </div>
            </div>
            <div class="button-group">
                <button class="btn-secondary" onclick="setControlMode('WEB')">Force WEB</button>
                <button class="btn-secondary" onclick="setControlMode('TCP')">Force TCP</button>
                <button class="btn-secondary" onclick="setControlMode('BUTTON')">Force BUTTON</button>
                <button class="btn-primary" onclick="setControlMode('AUTO')">Auto Mode</button>
            </div>
        </div>

        <div class="section" id="button-mode-config" style="display:none;">
            <h3>Button Configuration</h3>
            
            <div class="control-row">
                <label>Cycle Mode:</label>
                <select id="button-cycle-mode" onchange="setButtonCycleMode()">
                    <option value="2">2-Press (Pos 0-1)</option>
                    <option value="3">3-Press (Pos 0-1-2)</option>
                </select>
            </div>

            <div class="btn-config">
                <div class="pos-card" id="position-0-card">
                    <div class="pos-label">Position 0</div>
                    <select id="gesture-pos-0" onchange="setPositionGesture(0)">
                        <option value="0">Relax</option>
                        <option value="1" selected>HandClose</option>
                        <option value="2">HandOpen</option>
                        <option value="3">HookGrasp</option>
                        <option value="4">LateralGrasp</option>
                        <option value="5">ThumbFlex</option>
                        <option value="6">IndexFlex</option>
                        <option value="7">TripodGrasp</option>
                        <option value="8">SoftHandClose</option>
                    </select>
                </div>
                <div class="pos-card" id="position-1-card">
                    <div class="pos-label">Position 1</div>
                    <select id="gesture-pos-1" onchange="setPositionGesture(1)">
                        <option value="0">Relax</option>
                        <option value="1">HandClose</option>
                        <option value="2" selected>HandOpen</option>
                        <option value="3">HookGrasp</option>
                        <option value="4">LateralGrasp</option>
                        <option value="5">ThumbFlex</option>
                        <option value="6">IndexFlex</option>
                        <option value="7">TripodGrasp</option>
                        <option value="8">SoftHandClose</option>
                    </select>
                </div>
                <div class="pos-card" id="position-2-card">
                    <div class="pos-label">Position 2</div>
                    <select id="gesture-pos-2" onchange="setPositionGesture(2)">
                        <option value="0" selected>Relax</option>
                        <option value="1">HandClose</option>
                        <option value="2">HandOpen</option>
                        <option value="3">HookGrasp</option>
                        <option value="4">LateralGrasp</option>
                        <option value="5">ThumbFlex</option>
                        <option value="6">IndexFlex</option>
                        <option value="7">TripodGrasp</option>
                        <option value="8">SoftHandClose</option>
                    </select>
                </div>
            </div>

            <div class="pos-current">
                Current Position: <span id="current-position">0</span>
            </div>
        </div>

        <div class="section">
            <h3>Gestures</h3>
            <div class="button-group">
                <button class="btn-primary" onclick="setGesture(0)">Relax</button>
                <button class="btn-primary" onclick="setGesture(1)">HandClose</button>
                <button class="btn-primary" onclick="setGesture(2)">HandOpen</button>
                <button class="btn-primary" onclick="setGesture(3)">HookGrasp</button>
                <button class="btn-primary" onclick="setGesture(4)">LateralGrasp</button>
                <button class="btn-primary" onclick="setGesture(5)">ThumbFlex</button>
                <button class="btn-primary" onclick="setGesture(6)">IndexFlex</button>
                <button class="btn-primary" onclick="setGesture(7)">TripodGrasp</button>
                <button class="btn-primary" onclick="setGesture(8)">SoftHandClose</button>
            </div>
        </div>

        <div class="section">
            <h3>Pressure Control</h3>
            <div class="control-row">
                <label>Flexion:</label>
                <input type="number" id="flex-pressure" min="0" max="100" value="50">
                <button class="btn-primary" onclick="setPressure()">Set</button>
            </div>
            <div class="control-row">
                <label>Extension:</label>
                <input type="number" id="ext-pressure" min="0" max="100" value="50">
            </div>
        </div>

        <div class="section">
            <h3>Speed Control</h3>
            <div class="button-group">
                <button class="btn-secondary" onclick="setSpeed(0)">Stop (0)</button>
                <button class="btn-primary" onclick="setSpeed(1)">Slow (1)</button>
                <button class="btn-primary" onclick="setSpeed(2)">Medium (2)</button>
                <button class="btn-primary" onclick="setSpeed(3)">Fast (3)</button>
                <button class="btn-primary" onclick="setSpeed(4)">V.Fast (4)</button>
            </div>
        </div>

        <div class="section">
            <h3>Manual Finger Control</h3>
            <div class="control-row">
                <label>Finger States (6 digits, 0-3):</label>
                <input type="text" id="finger-states" value="000000" maxlength="6">
                <button class="btn-primary" onclick="setFingerStates()">Set</button>
            </div>
            <p style="font-size: 11px; color: #666; margin: 8px 0;">
                0=Relax, 1=Flex, 2=Extend, 3=Pinch | Positions: Thumb, Index, Middle, Ring, Pinky, Abd/Add
            </p>
        </div>

        <div class="section">
            <button class="btn-danger" onclick="emergencyStop()" style="width: 100%; padding: 15px; font-size: 16px;">
                EMERGENCY STOP
            </button>
        </div>
    </div>

    <script>
        function setGesture(g) {
            fetch('/set?gesture=' + g).then(response => response.text()).then(data => updateStatus());
        }
        function setPressure() {
            const flex = document.getElementById('flex-pressure').value;
            const ext = document.getElementById('ext-pressure').value;
            fetch('/set?pressure=' + flex + ':' + ext).then(response => response.text()).then(data => updateStatus());
        }
        function setSpeed(s) {
            fetch('/set?speed=' + s).then(response => response.text()).then(data => updateStatus());
        }
        function setFingerStates() {
            const states = document.getElementById('finger-states').value;
            fetch('/set?fingerstates=' + states).then(response => response.text()).then(data => updateStatus());
        }
        function emergencyStop() {
            fetch('/stop').then(response => response.text()).then(data => updateStatus());
        }
        function setControlMode(mode) {
            fetch('/set_mode?mode=' + mode).then(response => response.text()).then(data => updateStatus());
        }
        function setButtonCycleMode() {
            const mode = document.getElementById('button-cycle-mode').value;
            fetch('/set_button?cycle_mode=' + mode).then(response => response.text()).then(data => updateStatus());
        }
        function setPositionGesture(pos) {
            const gesture = document.getElementById('gesture-pos-' + pos).value;
            fetch('/set_button?position=' + pos + '&gesture=' + gesture).then(response => response.text()).then(data => updateStatus());
        }

        function updateStatus() {
            fetch('/status').then(response => response.json()).then(data => {
                document.getElementById('current-gesture').textContent = getGestureName(data.gesture);
                document.getElementById('current-flex').textContent = data.pressure_flex;
                document.getElementById('current-ext').textContent = data.pressure_ext;
                document.getElementById('current-speed').textContent = data.speed;
                document.getElementById('current-fingers').textContent = data.finger_states;
                document.getElementById('current-mode').textContent = data.control_mode;
                document.getElementById('mode-lock-status').textContent = data.mode_lock;
                document.getElementById('current-position').textContent = data.button_position;

                const modeStatus = document.getElementById('mode-status');
                modeStatus.textContent = data.control_mode + ' Mode';
                modeStatus.className = 'mode-indicator mode-' + data.control_mode.toLowerCase();

                document.getElementById('sta-status').textContent = data.sta_status;
                document.getElementById('sta-dot').className = 'status-dot ' + (data.sta_connected ? 'status-online' : 'status-offline');
                document.getElementById('tcp-status').textContent = data.tcp_status;
                document.getElementById('tcp-dot').className = 'status-dot ' + (data.tcp_connected ? 'status-online' : 'status-offline');
                document.getElementById('button-bridge-status').textContent = data.button_bridge_status;
                document.getElementById('button-bridge-dot').className = 'status-dot ' + (data.button_bridge_active ? 'status-online' : 'status-offline');

                document.getElementById('button-cycle-mode').value = data.button_cycle_mode;
                document.getElementById('gesture-pos-0').value = data.button_gestures[0];
                document.getElementById('gesture-pos-1').value = data.button_gestures[1];
                document.getElementById('gesture-pos-2').value = data.button_gestures[2];

                for (let i = 0; i < 3; i++) {
                    const card = document.getElementById('position-' + i + '-card');
                    if (i == data.button_position) {
                        card.classList.add('active');
                    } else {
                        card.classList.remove('active');
                    }
                }

                const btnConfig = document.getElementById('button-mode-config');
                if (data.control_mode === 'BUTTON' || data.mode_lock === 'FORCE_BUTTON_MODE') {
                    btnConfig.style.display = 'block';
                } else {
                    btnConfig.style.display = 'none';
                }
            });
        }

        function getGestureName(g) {
            const names = ['Relax', 'HandClose', 'HandOpen', 'HookGrasp', 'LateralGrasp', 'ThumbFlex', 'IndexFlex', 'TripodGrasp', 'SoftHandClose'];
            return names[g] || 'Unknown';
        }

        setInterval(updateStatus, 500);
        updateStatus();
    </script>
</body>
</html>
)rawliteral";

// ==================== Helper Functions (保持不变) ====================
int sanitizeGestureId(int g)
{
    if (g < 0 || g >= NUM_GESTURES)
    {
        return 0;
    }
    return g;
}

String getModeName(ControlMode mode)
{
    switch (mode)
    {
    case WEB_MODE:
        return "WEB";
    case TCP_MODE:
        return "TCP";
    case BUTTON_MODE:
        return "BUTTON";
    default:
        return "UNKNOWN";
    }
}

String getModeLockName(ControlModeLock lock)
{
    switch (lock)
    {
    case AUTO_MODE:
        return "AUTO";
    case FORCE_WEB_MODE:
        return "FORCE_WEB_MODE";
    case FORCE_TCP_MODE:
        return "FORCE_TCP_MODE";
    case FORCE_BUTTON_MODE:
        return "FORCE_BUTTON_MODE";
    default:
        return "UNKNOWN";
    }
}

// ==================== Web Server Handlers (保持不变但优化) ====================
void handleRoot()
{
    server.send(200, "text/html", html_page);
}

void handleSet()
{
    if (control_mode != WEB_MODE && mode_lock == AUTO_MODE)
    {
        server.send(403, "text/plain", "ERROR: Not in WEB mode");
        return;
    }

    if (server.hasArg("gesture"))
    {
        int newGesture = server.arg("gesture").toInt();
        newGesture = sanitizeGestureId(newGesture);
        gesture = newGesture;
        Serial.println("WEB: Set gesture " + String(gesture));
        status_changed = true;
    }

    if (server.hasArg("pressure"))
    {
        String pressureArg = server.arg("pressure");
        int colonIndex = pressureArg.indexOf(':');
        if (colonIndex > 0)
        {
            int flex = constrain(pressureArg.substring(0, colonIndex).toInt(), 0, 100);
            int ext = constrain(pressureArg.substring(colonIndex + 1).toInt(), 0, 100);
            pressure[0] = flex;
            pressure[1] = ext;
            Serial.println("WEB: Set pressure " + String(pressure[0]) + ":" + String(pressure[1]));
            status_changed = true;
        }
    }

    if (server.hasArg("speed"))
    {
        speed = constrain(server.arg("speed").toInt(), 0, 4);
        Serial.println("WEB: Set speed " + String(speed));
        status_changed = true;
    }

    if (server.hasArg("fingerstates"))
    {
        String stateArg = server.arg("fingerstates");
        if (stateArg.length() == 6)
        {
            bool valid = true;
            for (int i = 0; i < 6; i++)
            {
                if (stateArg.charAt(i) < '0' || stateArg.charAt(i) > '3')
                {
                    valid = false;
                    break;
                }
            }
            if (valid)
            {
                finger_states = stateArg;
                Serial.println("WEB: Set finger states " + finger_states);
                status_changed = true;
            }
        }
    }

    server.send(200, "text/plain", "OK");
}

void handleStop()
{
    emergencyStop();
    server.send(200, "text/plain", "EMERGENCY STOP ACTIVATED");
}

void handleStatus()
{
    StaticJsonDocument<1024> doc;

    doc["gesture"] = gesture;
    doc["pressure_flex"] = pressure[0];
    doc["pressure_ext"] = pressure[1];
    doc["speed"] = speed;
    doc["finger_states"] = finger_states;
    doc["control_mode"] = getModeName(control_mode);
    doc["mode_lock"] = getModeLockName(mode_lock);

    doc["sta_connected"] = (WiFi.status() == WL_CONNECTED);
    if (WiFi.status() == WL_CONNECTED)
    {
        doc["sta_status"] = WiFi.localIP().toString();
    }
    else
    {
        doc["sta_status"] = "Disconnected";
    }

    doc["tcp_connected"] = tcp_connected;
    doc["tcp_status"] = tcp_connected ? "Connected" : "Waiting...";

    unsigned long now = millis();
    bool button_bridge_active = (now - last_button_bridge_activity) < button_bridge_activity_timeout;
    doc["button_bridge_active"] = button_bridge_active;
    if (button_bridge_active)
    {
        doc["button_bridge_status"] = "Active (" + last_button_bridge_source + ")";
    }
    else
    {
        doc["button_bridge_status"] = "Inactive";
    }

    doc["button_cycle_mode"] = button_cycle_mode;
    JsonArray gestures = doc.createNestedArray("button_gestures");
    for (int i = 0; i < 3; i++)
    {
        gestures.add(button_gestures[i]);
    }
    doc["button_position"] = button_cycle_position;

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleSetMode()
{
    if (server.hasArg("mode"))
    {
        String modeArg = server.arg("mode");
        if (modeArg == "WEB")
        {
            mode_lock = FORCE_WEB_MODE;
            control_mode = WEB_MODE;
        }
        else if (modeArg == "TCP")
        {
            mode_lock = FORCE_TCP_MODE;
            control_mode = TCP_MODE;
        }
        else if (modeArg == "BUTTON")
        {
            mode_lock = FORCE_BUTTON_MODE;
            control_mode = BUTTON_MODE;
        }
        else if (modeArg == "AUTO")
        {
            mode_lock = AUTO_MODE;
        }
        Serial.println("Mode lock set to: " + getModeLockName(mode_lock));
        status_changed = true;
    }
    server.send(200, "text/plain", "OK");
}

void handleSetButton()
{
    if (server.hasArg("cycle_mode"))
    {
        int newMode = server.arg("cycle_mode").toInt();
        if (newMode == 2 || newMode == 3)
        {
            button_cycle_mode = newMode;
            Serial.println("Button cycle mode set to: " + String(button_cycle_mode));
            status_changed = true;
        }
    }

    if (server.hasArg("position") && server.hasArg("gesture"))
    {
        int pos = server.arg("position").toInt();
        int gest = server.arg("gesture").toInt();
        if (pos >= 0 && pos < 3)
        {
            button_gestures[pos] = sanitizeGestureId(gest);
            Serial.println("Position " + String(pos) + " set to gesture " + String(button_gestures[pos]));
            status_changed = true;
        }
    }

    server.send(200, "text/plain", "OK");
}

void handleNotFound()
{
    server.send(404, "text/plain", "Not Found");
}

// ==================== 修改后的按钮处理函数 ====================
void handleButtonPress()
{
    unsigned long now = millis();
    if (now - last_button_press < button_debounce_delay)
    {
        Serial.println("Button debounce, ignored");
        return;
    }
    last_button_press = now;

    Serial.println("Button press detected! Cycle position: " + String(button_cycle_position));

    gesture = button_gestures[button_cycle_position];
    Serial.println("Button: Set gesture to " + String(gesture));

    button_cycle_position++;
    if (button_cycle_position >= button_cycle_mode)
    {
        button_cycle_position = 0;
    }

    status_changed = true;
}

// ==================== 优化后的按钮消息检查函数 ====================
void checkButtonBridgeSerial()
{
    if (!button_bridge_serial_enabled)
    {
        return;
    }

    // 快速读取所有可用字节
    while (button_serial.available())
    {
        char c = button_serial.read();

        if (c == '\n' || c == '\r')
        {
            if (button_serial_buffer_idx > 0)
            {
                button_serial_buffer[button_serial_buffer_idx] = '\0';
                String message = String(button_serial_buffer);
                message.trim();

                if (message.length() > 0)
                {
                    Serial.println("Serial RX: " + message);
                    
                    // 立即加入队列
                    if (enqueueCommand(Command::BUTTON, message)) {
                        last_button_bridge_serial_activity = millis();
                        last_button_bridge_activity = last_button_bridge_serial_activity;
                        last_button_bridge_source = "serial";
                    }
                }
                button_serial_buffer_idx = 0;
            }
        }
        else if (button_serial_buffer_idx < sizeof(button_serial_buffer) - 1)
        {
            button_serial_buffer[button_serial_buffer_idx++] = c;
        }
        else
        {
            Serial.println("Serial buffer overflow!");
            button_serial_buffer_idx = 0;
        }
    }
}

void checkButtonBridgeWifi()
{
    if (!button_bridge_wifi_enabled)
    {
        return;
    }

    if (!button_udp_initialized)
    {
        if (button_udp.begin(button_udp_port))
        {
            button_udp_initialized = true;
            Serial.println("Button UDP initialized on port " + String(button_udp_port));
        }
        return;
    }

    // 快速读取所有UDP包
    int packetSize = button_udp.parsePacket();
    while (packetSize > 0)
    {
        char packetBuffer[256];
        int len = button_udp.read(packetBuffer, sizeof(packetBuffer) - 1);
        if (len > 0)
        {
            packetBuffer[len] = '\0';
            String message = String(packetBuffer);
            message.trim();

            if (message.length() > 0)
            {
                Serial.println("UDP RX: " + message);
                
                // 立即加入队列
                if (enqueueCommand(Command::BUTTON, message)) {
                    last_button_bridge_wifi_activity = millis();
                    last_button_bridge_activity = last_button_bridge_wifi_activity;
                    last_button_bridge_source = "wifi";
                }
            }
        }
        
        // 检查下一个包
        packetSize = button_udp.parsePacket();
    }
}

// ==================== 新增：处理命令队列 ====================
void processCommandQueue()
{
    // 每次循环处理多个命令以清空队列
    for (int i = 0; i < 3 && queueCount > 0; i++) {
        Command cmd;
        if (dequeueCommand(cmd)) {
            String message = cmd.data;
            
            if (message.startsWith("BTN:PRESS") || message == "BTN:ON")
            {
                handleButtonPress();
            }
            else if (message == "BTN:OFF")
            {
                // 可选：处理按钮释放
            }
            else
            {
                Serial.println("Unknown button command: " + message);
            }
        }
    }
}

// ==================== Control Mode Management (保持不变) ====================
void updateControlMode()
{
    if (mode_lock != AUTO_MODE)
    {
        switch (mode_lock)
        {
        case FORCE_WEB_MODE:
            control_mode = WEB_MODE;
            break;
        case FORCE_TCP_MODE:
            control_mode = TCP_MODE;
            break;
        case FORCE_BUTTON_MODE:
            control_mode = BUTTON_MODE;
            break;
        default:
            break;
        }
        return;
    }

    unsigned long now = millis();
    bool button_active = (now - last_button_bridge_activity) < button_bridge_activity_timeout;
    bool tcp_active = tcp_connected && ((now - last_tcp_command) < tcp_timeout);

    if (button_active)
    {
        control_mode = BUTTON_MODE;
    }
    else if (tcp_active)
    {
        control_mode = TCP_MODE;
    }
    else
    {
        control_mode = WEB_MODE;
    }
}

// ==================== TCP Client Handling (保持不变但优化) ====================
void checkTcpClient()
{
    if (!tcp_server_started)
    {
        return;
    }

    if (!tcpClient || !tcpClient.connected())
    {
        if (tcp_connected)
        {
            Serial.println("TCP client disconnected");
            tcp_connected = false;
            status_changed = true;
        }

        WiFiClient newClient = tcpServer.available();
        if (newClient)
        {
            if (tcpClient)
            {
                tcpClient.stop();
            }
            tcpClient = newClient;
            tcp_connected = true;
            tcp_buffer_idx = 0;
            last_tcp_command = millis();
            Serial.println("New TCP client connected from " + tcpClient.remoteIP().toString());
            status_changed = true;
        }
        return;
    }

    // 快速读取所有可用数据
    while (tcpClient.available())
    {
        char c = tcpClient.read();

        if (c == '\n' || c == '\r')
        {
            if (tcp_buffer_idx > 0)
            {
                tcp_command_buffer[tcp_buffer_idx] = '\0';
                String command = String(tcp_command_buffer);
                command.trim();

                if (command.length() > 0)
                {
                    Serial.println("TCP RX: " + command);
                    
                    // TCP命令立即处理（不使用队列）
                    processTcpCommand(command);
                    last_tcp_command = millis();
                }
                tcp_buffer_idx = 0;
            }
        }
        else if (tcp_buffer_idx < sizeof(tcp_command_buffer) - 1)
        {
            tcp_command_buffer[tcp_buffer_idx++] = c;
        }
        else
        {
            Serial.println("TCP buffer overflow!");
            tcpClient.println("ERROR: Command too long");
            tcp_buffer_idx = 0;
        }
    }
}

void processTcpCommand(const String &command)
{
    if (control_mode != TCP_MODE && mode_lock == AUTO_MODE)
    {
        tcpClient.println("ERROR: Not in TCP mode");
        tcpClient.flush();
        return;
    }

    int colonIndex = command.indexOf(':');
    if (colonIndex > 0)
    {
        String cmdType = command.substring(0, colonIndex);
        String params = command.substring(colonIndex + 1);

        if (cmdType == "g")
        {
            int newGesture = params.toInt();
            newGesture = sanitizeGestureId(newGesture);
            gesture = newGesture;
            Serial.println("TCP: Set gesture " + String(gesture));
            tcpClient.println("OK");
            status_changed = true;
        }
        else if (cmdType == "p")
        {
            int colonIndex2 = params.indexOf(':');
            if (colonIndex2 > 0)
            {
                int flex = constrain(params.substring(0, colonIndex2).toInt(), 0, 100);
                int ext = constrain(params.substring(colonIndex2 + 1).toInt(), 0, 100);
                pressure[0] = flex;
                pressure[1] = ext;
                Serial.println("TCP: Set pressure " + String(pressure[0]) + ":" + String(pressure[1]));
                tcpClient.println("OK");
                status_changed = true;
            }
            else
            {
                tcpClient.println("ERROR: Invalid pressure format");
            }
        }
        else if (cmdType == "s")
        {
            speed = constrain(params.toInt(), 0, 4);
            Serial.println("TCP: Set speed " + String(speed));
            tcpClient.println("OK");
            status_changed = true;
        }
        else if (cmdType == "f")
        {
            if (params.length() == 6)
            {
                bool valid = true;
                for (int i = 0; i < 6; i++)
                {
                    if (params.charAt(i) < '0' || params.charAt(i) > '3')
                    {
                        valid = false;
                        break;
                    }
                }
                if (valid)
                {
                    finger_states = params;
                    Serial.println("TCP: Set finger states " + finger_states);
                    tcpClient.println("OK");
                    status_changed = true;
                }
                else
                {
                    tcpClient.println("ERROR: Invalid finger states");
                }
            }
            else
            {
                tcpClient.println("ERROR: Finger states must be 6 digits");
            }
        }
        else
        {
            tcpClient.println("ERROR: Unknown command");
        }
    }
    else if (command == "stop")
    {
        emergencyStop();
        tcpClient.println("OK");
    }
    else
    {
        tcpClient.println("ERROR: Invalid command format");
    }
    tcpClient.flush();
}

// ==================== Actuator Update (保持不变) ====================
void updateActuators()
{
    gestureToFingerStates();
    setFingerStates();

    if (dac_available)
    {
        setPressureDAC();
        setSpeedDAC();
    }
}

void gestureToFingerStates()
{
    static int lastGesture = -1;

    if (gesture != lastGesture)
    {
        String oldFingerStates = finger_states;
        lastGesture = gesture;

        finger_states = GESTURE_TO_FINGER_STATES_MAP[gesture];
        status_changed = true;
    }
}

void setFingerStates()
{
    if (finger_states.length() != 6) return;

    for (int i = 0; i < 5; i++)
    {
        char state = finger_states.charAt(i);

        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);

        switch (state)
        {
        case '1':
            digitalWrite(flexion_pins[i], HIGH);
            break;
        case '2':
            digitalWrite(extension_pins[i], HIGH);
            break;
        case '3':
            digitalWrite(pinching_pins[i], HIGH);
            break;
        default:
            break;
        }
    }

    char abd_state = finger_states.charAt(5);
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);

    if (abd_state == '1')
    {
        digitalWrite(adduction_pin, HIGH);
    }
    else if (abd_state == '2')
    {
        digitalWrite(abduction_pin, HIGH);
    }
}

void setPressureDAC()
{
    if (!dac_available) return;

    int flex_dac = (pressure[0] * 4095) / 100;
    int ext_dac = (pressure[1] * 4095) / 100;

    dac.setChannelValue(MCP4728_CHANNEL_A, ext_dac);
    dac.setChannelValue(MCP4728_CHANNEL_B, flex_dac);
}

void setSpeedDAC()
{
    if (!dac_available) return;

    int valueC = 0, valueD = 0;

    switch (speed)
    {
    case 0:
        valueC = 0;
        valueD = 0;
        break;
    case 1:
        valueC = 2048;
        valueD = 0;
        break;
    case 2:
        valueC = 2048;
        valueD = 2048;
        break;
    case 3:
        valueC = 4095;
        valueD = 2048;
        break;
    case 4:
        valueC = 4095;
        valueD = 4095;
        break;
    }

    dac.setChannelValue(MCP4728_CHANNEL_C, valueD);
    dac.setChannelValue(MCP4728_CHANNEL_D, valueC);
}

void emergencyStop()
{
    Serial.println("EMERGENCY STOP!");

    gesture = 0;
    pressure[0] = 0;
    pressure[1] = 0;
    speed = 0;
    finger_states = "000000";
    status_changed = true;

    for (int i = 0; i < 5; i++)
    {
        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);
    }
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);

    if (dac_available)
    {
        dac.setChannelValue(MCP4728_CHANNEL_A, 0);
        dac.setChannelValue(MCP4728_CHANNEL_B, 0);
        dac.setChannelValue(MCP4728_CHANNEL_C, 0);
        dac.setChannelValue(MCP4728_CHANNEL_D, 0);
    }
}

// ==================== Setup (优化) ====================
void setup()
{
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== ESP32 Glove Control (Optimized V4.1) ===");

    // 硬件初始化
    for (int i = 0; i < 5; i++)
    {
        pinMode(flexion_pins[i], OUTPUT);
        pinMode(extension_pins[i], OUTPUT);
        pinMode(pinching_pins[i], OUTPUT);
        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);
    }
    pinMode(abduction_pin, OUTPUT);
    pinMode(adduction_pin, OUTPUT);
    pinMode(emergency_pin, INPUT_PULLUP);
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);

    // I2C和DAC初始化
    Wire.begin(sda_pin, scl_pin);
    if (dac.begin())
    {
        Serial.println("DAC initialized successfully");
        dac_available = true;
    }
    else
    {
        Serial.println("DAC initialization failed - running without DAC");
        dac_available = false;
    }

    // WiFi AP初始化
    WiFi.disconnect(true); // 清除之前的WiFi配置
    delay(100);
    WiFi.mode(WIFI_AP_STA);
    delay(100);
    
    // 配置AP参数
    WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
    
    // 启动AP
    bool apStarted = WiFi.softAP(ap_ssid, ap_password);
    if (apStarted) {
        Serial.println("AP started successfully");
    } else {
        Serial.println("AP start failed!");
    }
    
    delay(500); // 增加延迟确保AP完全启动
    
    IPAddress IP = WiFi.softAPIP();
    Serial.print("AP IP address: ");
    Serial.println(IP);
    Serial.print("AP SSID: ");
    Serial.println(ap_ssid);
    Serial.print("AP Password: ");
    Serial.println(ap_password);

    // WiFi STA初始化（非阻塞）
    if (strlen(sta_ssid) > 0)
    {
        WiFi.begin(sta_ssid, sta_password);
        Serial.println("Connecting to WiFi (non-blocking)...");
    }

    // TCP服务器初始化
    tcpServer.begin();
    tcp_server_started = true;
    Serial.println("TCP server started on port " + String(tcp_port));

    // 按钮串口初始化
    if (button_bridge_serial_enabled)
    {
        button_serial.begin(115200, SERIAL_8N1, button_serial_rx_pin, button_serial_tx_pin);
        Serial.println("Button bridge serial initialized");
    }

    // Web服务器路由
    server.on("/", handleRoot);
    server.on("/set", handleSet);
    server.on("/stop", handleStop);
    server.on("/status", handleStatus);
    server.on("/set_mode", handleSetMode);
    server.on("/set_button", handleSetButton);
    server.onNotFound(handleNotFound);
    server.begin();
    Serial.println("Web server started");

    Serial.println("=== Setup complete ===\n");
}

// ==================== 优化后的Loop函数 ====================
void loop()
{
    // 优先级1: 按钮输入检查（最高优先级，最快响应）
    checkButtonBridgeSerial();
    checkButtonBridgeWifi();
    
    // 优先级2: 处理命令队列
    processCommandQueue();
    
    // 优先级3: TCP客户端检查
    checkTcpClient();
    
    // 优先级4: Web服务器处理
    server.handleClient();
    
    // 优先级5: 控制模式更新
    updateControlMode();
    
    // 优先级6: 执行器更新（如果状态改变）
    if (status_changed)
    {
        updateActuators();
        status_changed = false;
    }
    
    // 优先级7: WiFi状态检查（降低频率，避免阻塞）
    static unsigned long last_wifi_check = 0;
    unsigned long now = millis();
    if (now - last_wifi_check > 2000) // 每2秒检查一次
    {
        last_wifi_check = now;
        if (WiFi.status() != WL_CONNECTED && strlen(sta_ssid) > 0)
        {
            // 非阻塞重连
            WiFi.reconnect();
        }
    }
    
    // 优先级8: 紧急停止检查
    if (digitalRead(emergency_pin) == LOW)
    {
        emergencyStop();
        delay(100);
    }
    
    // 不添加任何delay，保持最快循环
}
