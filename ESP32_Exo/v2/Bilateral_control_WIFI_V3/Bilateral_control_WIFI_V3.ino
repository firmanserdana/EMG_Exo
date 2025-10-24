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
int speed = 1;
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
const unsigned long button_debounce_delay = 200;
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

// ==================== HTML Page ====================
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
        <h1>ESP32 Glove Control</h1>
        
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
                        <option value="7">MRPFlex</option>
                        <option value="8">IndexPoint</option>
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
                        <option value="7">MRPFlex</option>
                        <option value="8">IndexPoint</option>
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
                        <option value="7">MRPFlex</option>
                        <option value="8">IndexPoint</option>
                    </select>
                </div>
            </div>

            <div class="pos-current">
                Current: <span id="current-position">0</span>
                <button class="btn-secondary" onclick="resetButtonCycle()" style="margin-left: 10px;">Reset</button>
            </div>
        </div>

        <div class="section">
            <h3>Gesture Control</h3>
            <div class="button-group">
                <button class="btn-primary" onclick="setGesture(0)">Relax</button>
                <button class="btn-primary" onclick="setGesture(1)">HandClose</button>
                <button class="btn-primary" onclick="setGesture(2)">HandOpen</button>
                <button class="btn-primary" onclick="setGesture(3)">HookGrasp</button>
                <button class="btn-primary" onclick="setGesture(4)">LateralGrasp</button>
                <button class="btn-primary" onclick="setGesture(5)">ThumbFlex</button>
                <button class="btn-primary" onclick="setGesture(6)">IndexFlex</button>
                <button class="btn-primary" onclick="setGesture(7)">MRPFlex</button>
                <button class="btn-primary" onclick="setGesture(8)">IndexPoint</button>
            </div>
        </div>

        <div class="section">
            <h3>Manual Control</h3>
            <div class="control-row">
                <label>Flex Pressure (0-100):</label>
                <input type="number" id="flex-pressure" min="0" max="100" value="50">
                <button class="btn-secondary" onclick="setPressure()">Set</button>
            </div>
            <div class="control-row">
                <label>Ext Pressure (0-100):</label>
                <input type="number" id="ext-pressure" min="0" max="100" value="50">
            </div>
            <div class="control-row">
                <label>Speed (0-4):</label>
                <input type="number" id="speed-level" min="0" max="4" value="1">
                <button class="btn-secondary" onclick="setSpeed()">Set</button>
            </div>
            <div class="control-row">
                <label>Finger States (6 digits):</label>
                <input type="text" id="finger-states" maxlength="6" value="000000" style="width: 100px;">
                <button class="btn-secondary" onclick="setFingerStates()">Set</button>
            </div>
        </div>

        <div class="section">
            <h3>Emergency</h3>
            <button class="btn-danger" onclick="emergencyStop()" style="font-size: 16px; padding: 12px 24px;">EMERGENCY STOP</button>
        </div>
    </div>

    <script>
        const gestureNames = ["Relax", "HandClose", "HandOpen", "HookGrasp", "LateralGrasp", "ThumbFlex", "IndexFlex", "MRPFlex", "IndexPoint"];
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const modeElement = document.getElementById('mode-status');
                    if (data.mode === 'TCP') {
                        modeElement.className = 'mode-indicator mode-tcp';
                        modeElement.textContent = 'TCP Mode';
                    } else if (data.mode === 'BUTTON') {
                        modeElement.className = 'mode-indicator mode-web';
                        modeElement.textContent = 'Button Mode';
                    } else {
                        modeElement.className = 'mode-indicator mode-web';
                        modeElement.textContent = 'Web Mode';
                    }
                    
                    document.getElementById('button-mode-config').style.display = data.mode === 'BUTTON' ? 'block' : 'none';
                    
                    const staDot = document.getElementById('sta-dot');
                    const staStatus = document.getElementById('sta-status');
                    if (data.sta_connected) {
                        staDot.className = 'status-dot status-online';
                        staStatus.textContent = data.sta_ip;
                    } else {
                        staDot.className = 'status-dot status-offline';
                        staStatus.textContent = 'Disconnected';
                    }
                    
                    const tcpDot = document.getElementById('tcp-dot');
                    const tcpStatus = document.getElementById('tcp-status');
                    if (data.tcp_connected) {
                        tcpDot.className = 'status-dot status-online';
                        tcpStatus.textContent = 'Connected';
                    } else {
                        tcpDot.className = 'status-dot status-offline';
                        tcpStatus.textContent = 'Waiting...';
                    }
                    
                    const buttonBridgeDot = document.getElementById('button-bridge-dot');
                    const buttonBridgeStatus = document.getElementById('button-bridge-status');
                    if (data.button_bridge) {
                        const serialActive = !!data.button_bridge.serial_active;
                        const wifiActive = !!data.button_bridge.wifi_active;
                        const active = serialActive || wifiActive;
                        buttonBridgeDot.className = 'status-dot ' + (active ? 'status-online' : 'status-offline');
                        if (active) {
                            const channels = [];
                            if (serialActive) channels.push('Serial');
                            if (wifiActive) channels.push('WiFi');
                            buttonBridgeStatus.textContent = channels.join('+');
                        } else {
                            buttonBridgeStatus.textContent = 'No activity';
                        }
                    }
                    
                    document.getElementById('current-gesture').textContent = gestureNames[data.gesture] || 'Unknown';
                    document.getElementById('current-flex').textContent = data.pressure[0];
                    document.getElementById('current-ext').textContent = data.pressure[1];
                    document.getElementById('current-speed').textContent = data.speed;
                    document.getElementById('current-fingers').textContent = data.finger_states;
                    document.getElementById('current-mode').textContent = data.mode;
                    document.getElementById('mode-lock-status').textContent = data.mode_lock;
                    document.getElementById('flex-pressure').value = data.pressure[0];
                    document.getElementById('ext-pressure').value = data.pressure[1];
                    document.getElementById('speed-level').value = data.speed;
                    document.getElementById('finger-states').value = data.finger_states;

                    if (data.button_config) {
                        const config = data.button_config;
                        document.getElementById('button-cycle-mode').value = String(config.cycle_mode);
                        
                        for (let i = 0; i < 3; i++) {
                            const select = document.getElementById('gesture-pos-' + i);
                            if (select && config.gestures && config.gestures[i] !== undefined) {
                                select.value = String(config.gestures[i]);
                            }
                            
                            const card = document.getElementById('position-' + i + '-card');
                            if (card) {
                                if (config.position === i) {
                                    card.classList.add('active');
                                } else {
                                    card.classList.remove('active');
                                }
                            }
                        }
                        
                        document.getElementById('current-position').textContent = config.position;
                        document.getElementById('position-2-card').style.opacity = config.cycle_mode === 3 ? '1' : '0.5';
                    }
                })
                .catch(error => console.log('Update failed'));
        }

        function sendCommand(endpoint, params = '') {
            const url = params ? `/${endpoint}?${params}` : `/${endpoint}`;
            return fetch(url).catch(error => console.log('Command failed'));
        }

        function setGesture(g) { sendCommand('gesture', `value=${g}`); }
        function setPressure() {
            const flex = document.getElementById('flex-pressure').value;
            const ext = document.getElementById('ext-pressure').value;
            sendCommand('pressure', `flex=${flex}&ext=${ext}`);
        }
        function setSpeed() { sendCommand('speed', `value=${document.getElementById('speed-level').value}`); }
        function setFingerStates() {
            const states = document.getElementById('finger-states').value;
            if (states.length === 6 && /^[0-3]+$/.test(states)) {
                sendCommand('fingers', `value=${states}`);
            } else {
                alert('Must be 6 digits (0-3)');
            }
        }
        function emergencyStop() { sendCommand('stop'); }
        function setControlMode(mode) { sendCommand('mode', `value=${mode}`).then(() => setTimeout(updateStatus, 100)); }
        function setButtonCycleMode() { sendCommand('button-cycle-mode', `value=${document.getElementById('button-cycle-mode').value}`).then(() => setTimeout(updateStatus, 100)); }
        function setPositionGesture(position) { sendCommand('button-position', `pos=${position}&gesture=${document.getElementById('gesture-pos-' + position).value}`).then(() => setTimeout(updateStatus, 100)); }
        function resetButtonCycle() { sendCommand('button-reset').then(() => setTimeout(updateStatus, 100)); }

        setInterval(updateStatus, 1000);
        updateStatus();
    </script>
</body>
</html>)rawliteral";

// ==================== Function Declarations ====================
void initHardware();
void initNetworks();
void initDAC();
void initButtonBridge();
void handleWebRequests();
void handleTCPCommands();
void pollButtonBridgeInterfaces();
void processButtonCommand(const String &command, const char *source);
void advanceButtonCycle(const char *source);
void setButtonPosition(int position, const char *source);
void applyButtonGesture(const char *source);
int sanitizeGestureId(int gestureId);
bool extractButtonCommandValue(const String &normalized, int &value);
void updateActuators();
void gestureToFingerStates();
void setFingerStates();
void setPressureDAC();
void setSpeedDAC();
void parseAndExecuteTCPCommand(String command);
void emergencyStop();
void handleButtonControl();

// ==================== Main Program ====================
void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== ESP32 Glove Control System ===");
    Serial.println("Initializing...");

    initHardware();
    initNetworks();
    initButtonBridge();
    initDAC();

    Serial.println("=== System Ready ===");
    Serial.println("Web Interface: 192.168.4.1");
    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.print("TCP Server (STA): ");
        Serial.print(WiFi.localIP());
        Serial.print(":");
        Serial.println(tcp_port);
    }
    Serial.print("TCP Server (AP): ");
    Serial.print(WiFi.softAPIP());
    Serial.print(":");
    Serial.println(tcp_port);
    Serial.println("====================");
}

void loop()
{
    if (digitalRead(emergency_pin) == LOW)
    {
        emergencyStop();
        delay(100);
        return;
    }

    server.handleClient();
    handleTCPCommands();
    handleButtonControl();

    static unsigned long lastServerCheck = 0;
    if (millis() - lastServerCheck > 30000)
    {
        lastServerCheck = millis();
        Serial.println("TCP Server Status Check:");
        Serial.print("  Server running on port ");
        Serial.println(tcp_port);
        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.print("  Available at STA IP: ");
            Serial.print(WiFi.localIP());
            Serial.print(":");
            Serial.println(tcp_port);
        }
        Serial.print("  Available at AP IP: ");
        Serial.print(WiFi.softAPIP());
        Serial.print(":");
        Serial.println(tcp_port);
        Serial.print("  TCP Connected: ");
        Serial.println(tcp_connected ? "YES" : "NO");
    }

    if (tcp_connected && (millis() - last_tcp_command > tcp_timeout))
    {
        Serial.println("TCP connection timeout");
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    if (tcp_connected && !tcpClient.connected())
    {
        Serial.println("TCP client disconnected");
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    updateActuators();

    delay(5);
}

// ==================== Hardware Initialization ====================
void initHardware()
{
    Serial.println("Initializing hardware...");

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

    Serial.println("Hardware initialized");
}

// ==================== Remote Button Bridge ====================
void initButtonBridge()
{
    Serial.println("Initializing remote button bridge...");

    if (button_bridge_serial_enabled)
    {
        button_serial.begin(115200, SERIAL_8N1, button_serial_rx_pin, button_serial_tx_pin);
        button_serial_buffer_idx = 0;
        button_serial.flush();
        Serial.print("  Serial bridge RX pin: ");
        Serial.print(button_serial_rx_pin);
        Serial.print(", TX pin: ");
        Serial.println(button_serial_tx_pin);
    }

    if (button_bridge_wifi_enabled)
    {
        button_udp_initialized = button_udp.begin(button_udp_port);
        if (button_udp_initialized)
        {
            Serial.print("  UDP bridge listening on port ");
            Serial.println(button_udp_port);
        }
    }

    Serial.println("Remote button bridge ready");
}

void pollButtonBridgeInterfaces()
{
    if (button_bridge_serial_enabled)
    {
        while (button_serial.available())
        {
            char incoming = button_serial.read();
            if (incoming == '\r' || incoming == '\n')
            {
                if (button_serial_buffer_idx > 0)
                {
                    button_serial_buffer[button_serial_buffer_idx] = '\0';
                    processButtonCommand(String(button_serial_buffer), "SERIAL");
                    button_serial_buffer_idx = 0;
                }
            }
            else if (button_serial_buffer_idx < sizeof(button_serial_buffer) - 1)
            {
                button_serial_buffer[button_serial_buffer_idx++] = incoming;
            }
        }
    }

    if (button_bridge_wifi_enabled && button_udp_initialized)
    {
        int packetSize = button_udp.parsePacket();
        while (packetSize > 0)
        {
            char udp_buffer[64];
            int len = button_udp.read(udp_buffer, sizeof(udp_buffer) - 1);
            if (len > 0)
            {
                udp_buffer[len] = '\0';
                processButtonCommand(String(udp_buffer), "UDP");
            }
            packetSize = button_udp.parsePacket();
        }
    }

    unsigned long now = millis();
    if (button_bridge_serial_enabled && last_button_bridge_serial_activity > 0 && 
        now - last_button_bridge_serial_activity > button_bridge_activity_timeout)
    {
        last_button_bridge_serial_activity = 0;
    }
    if (button_bridge_wifi_enabled && last_button_bridge_wifi_activity > 0 && 
        now - last_button_bridge_wifi_activity > button_bridge_activity_timeout)
    {
        last_button_bridge_wifi_activity = 0;
    }
    if (last_button_bridge_activity > 0 && now - last_button_bridge_activity > button_bridge_activity_timeout)
    {
        last_button_bridge_activity = 0;
        last_button_bridge_source = "none";
    }
}

bool extractButtonCommandValue(const String &normalized, int &value)
{
    int delimiterIndex = normalized.indexOf(':');
    if (delimiterIndex < 0) delimiterIndex = normalized.indexOf('=');
    if (delimiterIndex < 0) delimiterIndex = normalized.indexOf(' ');

    if (delimiterIndex > 0 && delimiterIndex < normalized.length() - 1)
    {
        value = normalized.substring(delimiterIndex + 1).toInt();
        return true;
    }
    return false;
}

void processButtonCommand(const String &rawCommand, const char *source)
{
    String command = rawCommand;
    command.trim();
    if (command.length() == 0) return;

    unsigned long now = millis();
    last_button_bridge_activity = now;
    last_button_bridge_source = source;

    if (strcmp(source, "SERIAL") == 0)
    {
        last_button_bridge_serial_activity = now;
    }
    else if (strcmp(source, "UDP") == 0)
    {
        last_button_bridge_wifi_activity = now;
    }

    String normalized = command;
    normalized.toUpperCase();
    if (normalized.startsWith("BTN:"))
    {
        normalized.remove(0, 4);
    }

    bool recognized = false;

    if (normalized == "PRESS" || normalized == "P" || normalized == "TOGGLE")
    {
        recognized = true;
        advanceButtonCycle(source);
    }
    else if (normalized.startsWith("POSITION") || normalized.startsWith("POS"))
    {
        recognized = true;
        int position = -1;
        if (extractButtonCommandValue(normalized, position))
        {
            if (position >= 0 && position <= 2)
            {
                setButtonPosition(position, source);
            }
        }
    }
    else if (normalized == "RESET")
    {
        recognized = true;
        setButtonPosition(0, source);
    }

    if (recognized)
    {
        status_changed = true;
    }
}

void advanceButtonCycle(const char *source)
{
    if (control_mode != BUTTON_MODE)
    {
        Serial.printf("[BUTTON][%s] Ignored - not in BUTTON mode\n", source);
        return;
    }

    unsigned long now = millis();
    if (now - last_button_press < button_debounce_delay)
    {
        return;
    }
    last_button_press = now;

    int next_position;
    if (button_cycle_mode == 2)
    {
        next_position = (button_cycle_position == 0) ? 1 : 0;
    }
    else
    {
        next_position = (button_cycle_position + 1) % 3;
    }

    setButtonPosition(next_position, source);
}

void setButtonPosition(int position, const char *source)
{
    position = constrain(position, 0, 2);
    
    if (button_cycle_mode == 2 && position > 1)
    {
        position = 0;
    }

    button_cycle_position = position;
    applyButtonGesture(source);
    status_changed = true;

    Serial.printf("[BUTTON][%s] Position set to %d\n", source, button_cycle_position);
}

void applyButtonGesture(const char *source)
{
    if (control_mode == BUTTON_MODE)
    {
        int target_gesture = sanitizeGestureId(button_gestures[button_cycle_position]);
        if (gesture != target_gesture)
        {
            gesture = target_gesture;
            Serial.printf("[BUTTON][%s] Applied gesture %d\n", source, gesture);
        }
    }
}

int sanitizeGestureId(int gestureId)
{
    return constrain(gestureId, 0, NUM_GESTURES - 1);
}

void handleButtonControl()
{
    pollButtonBridgeInterfaces();
}

// ==================== Network Initialization ====================
void initNetworks()
{
    Serial.println("Initializing networks...");

    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(ap_ssid, ap_password);
    Serial.print("AP started: ");
    Serial.println(WiFi.softAPIP());

    WiFi.begin(sta_ssid, sta_password);
    Serial.print("Connecting to ");
    Serial.print(sta_ssid);

    int connect_timeout = 20;
    while (WiFi.status() != WL_CONNECTED && connect_timeout > 0)
    {
        delay(500);
        Serial.print(".");
        connect_timeout--;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("\nSTA connected!");
        Serial.print("STA IP: ");
        Serial.println(WiFi.localIP());
    }
    else
    {
        Serial.println("\nSTA connection failed, AP only mode");
    }

    tcpServer.begin();
    tcpServer.setNoDelay(true);
    tcp_server_started = true;
    Serial.println("TCP server started");

    server.on("/", []() { server.send(200, "text/html", html_page); });

    server.on("/status", []()
              {
        StaticJsonDocument<1024> json_doc;
        char json_buffer[1024];

        json_doc["mode"] = (control_mode == TCP_MODE ? "TCP" : 
                           (control_mode == BUTTON_MODE ? "BUTTON" : "WEB"));
        json_doc["mode_lock"] = (mode_lock == AUTO_MODE ? "AUTO" : 
                                (mode_lock == FORCE_WEB_MODE ? "FORCE_WEB" : 
                                (mode_lock == FORCE_TCP_MODE ? "FORCE_TCP" : "FORCE_BUTTON")));
        json_doc["sta_connected"] = (WiFi.status() == WL_CONNECTED);
        json_doc["sta_ip"] = WiFi.localIP().toString();
        json_doc["tcp_connected"] = tcp_connected;
        json_doc["tcp_client_ip"] = (tcp_connected ? tcpClient.remoteIP().toString() : "none");
        json_doc["gesture"] = gesture;
        
        JsonArray pressure_array = json_doc.createNestedArray("pressure");
        pressure_array.add(pressure[0]);
        pressure_array.add(pressure[1]);
        
        json_doc["speed"] = speed;
        json_doc["finger_states"] = finger_states;

        bool serialActive = button_bridge_serial_enabled && last_button_bridge_serial_activity > 0 && 
                           (millis() - last_button_bridge_serial_activity) <= button_bridge_activity_timeout;
        bool wifiActive = button_bridge_wifi_enabled && last_button_bridge_wifi_activity > 0 && 
                         (millis() - last_button_bridge_wifi_activity) <= button_bridge_activity_timeout;

        JsonObject buttonBridge = json_doc.createNestedObject("button_bridge");
        buttonBridge["serial_active"] = serialActive;
        buttonBridge["wifi_active"] = wifiActive;
        buttonBridge["last_source"] = last_button_bridge_source;
        buttonBridge["last_ms"] = (last_button_bridge_activity > 0) ? (millis() - last_button_bridge_activity) : -1;

        JsonObject buttonConfig = json_doc.createNestedObject("button_config");
        JsonArray gesturesArray = buttonConfig.createNestedArray("gestures");
        for (int i = 0; i < 3; i++)
        {
            gesturesArray.add(button_gestures[i]);
        }
        buttonConfig["cycle_mode"] = button_cycle_mode;
        buttonConfig["position"] = button_cycle_position;

        serializeJson(json_doc, json_buffer);
        server.send(200, "application/json", json_buffer); });

    server.on("/gesture", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            int newGesture = server.arg("value").toInt();
            newGesture = sanitizeGestureId(newGesture);
            gesture = newGesture;
            Serial.println("Web: Set gesture " + String(gesture));
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/pressure", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("flex") && server.hasArg("ext")) {
            pressure[0] = constrain(server.arg("flex").toInt(), 0, 100);
            pressure[1] = constrain(server.arg("ext").toInt(), 0, 100);
            Serial.println("Web: Set pressure " + String(pressure[0]) + ":" + String(pressure[1]));
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/speed", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            speed = constrain(server.arg("value").toInt(), 0, 4);
            Serial.println("Web: Set speed " + String(speed));
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/fingers", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            String states = server.arg("value");
            if (states.length() == 6) {
                finger_states = states;
                Serial.println("Web: Set finger states " + finger_states);
                status_changed = true;
            }
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/mode", []()
              {
        if (server.hasArg("value")) {
            String mode = server.arg("value");
            mode.toUpperCase();
            
            if (mode == "WEB") {
                mode_lock = FORCE_WEB_MODE;
                control_mode = WEB_MODE;
                if (tcp_connected) {
                    tcpClient.stop();
                    tcp_connected = false;
                }
                setButtonPosition(0, "WEB");
                Serial.println("Web: Control mode forced to WEB");
            }
            else if (mode == "TCP") {
                mode_lock = FORCE_TCP_MODE;
                control_mode = TCP_MODE;
                setButtonPosition(0, "WEB");
                Serial.println("Web: Control mode forced to TCP");
            }
            else if (mode == "BUTTON") {
                mode_lock = FORCE_BUTTON_MODE;
                control_mode = BUTTON_MODE;
                if (tcp_connected) {
                    tcpClient.stop();
                    tcp_connected = false;
                }
                setButtonPosition(0, "WEB");
                applyButtonGesture("WEB");
                Serial.println("Web: Control mode forced to BUTTON");
            }
            else if (mode == "AUTO") {
                mode_lock = AUTO_MODE;
                control_mode = tcp_connected ? TCP_MODE : WEB_MODE;
                if (control_mode != BUTTON_MODE) {
                    setButtonPosition(0, "WEB");
                }
                Serial.println("Web: Control mode set to AUTO");
            }
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/stop", []()
              {
        emergencyStop();
        server.send(200, "text/plain", "OK"); });

    server.on("/button-cycle-mode", []()
              {
        if (server.hasArg("value")) {
            int mode = server.arg("value").toInt();
            if (mode == 2 || mode == 3) {
                button_cycle_mode = mode;
                if (button_cycle_mode == 2 && button_cycle_position > 1) {
                    setButtonPosition(0, "WEB");
                }
                Serial.print("Web: Button cycle mode set to ");
                Serial.println(button_cycle_mode);
                status_changed = true;
            }
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/button-position", []()
              {
        if (server.hasArg("pos") && server.hasArg("gesture")) {
            int pos = server.arg("pos").toInt();
            int gest = server.arg("gesture").toInt();
            if (pos >= 0 && pos <= 2) {
                button_gestures[pos] = sanitizeGestureId(gest);
                Serial.printf("Web: Position %d set to gesture %d\n", pos, button_gestures[pos]);
                if (control_mode == BUTTON_MODE && button_cycle_position == pos) {
                    applyButtonGesture("WEB");
                }
                status_changed = true;
            }
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/button-reset", []()
              {
        setButtonPosition(0, "WEB");
        status_changed = true;
        server.send(200, "text/plain", "OK"); });

    server.begin();
    Serial.println("Web server started");
}

// ==================== DAC Initialization ====================
void initDAC()
{
    Serial.println("Initializing DAC...");
    Wire.begin(sda_pin, scl_pin);

    if (dac.begin())
    {
        dac_available = true;
        dac.setChannelValue(MCP4728_CHANNEL_A, 0);
        dac.setChannelValue(MCP4728_CHANNEL_B, 0);
        dac.setChannelValue(MCP4728_CHANNEL_C, 0);
        dac.setChannelValue(MCP4728_CHANNEL_D, 0);
        Serial.println("DAC initialized successfully");
    }
    else
    {
        dac_available = false;
        Serial.println("DAC initialization failed");
    }
}

// ==================== TCP Command Handler ====================
void handleTCPCommands()
{
    if (!tcp_connected && tcpServer.hasClient())
    {
        if (mode_lock != FORCE_WEB_MODE)
        {
            if (tcpClient) tcpClient.stop();

            tcpClient = tcpServer.available();
            if (tcpClient)
            {
                tcp_connected = true;
                if (mode_lock == AUTO_MODE)
                {
                    control_mode = TCP_MODE;
                }
                tcp_buffer_idx = 0;
                Serial.print("TCP client connected from: ");
                Serial.println(tcpClient.remoteIP());

                tcpClient.println("ESP32 Glove Control Ready");
                tcpClient.flush();

                last_tcp_command = millis();
                status_changed = true;
            }
        }
        else
        {
            WiFiClient rejectClient = tcpServer.available();
            if (rejectClient)
            {
                rejectClient.println("ERROR: ESP32 forced to WEB mode");
                rejectClient.stop();
            }
        }
    }

    if (tcp_connected && tcpClient.connected())
    {
        while (tcpClient.available() && tcp_buffer_idx < sizeof(tcp_command_buffer) - 1)
        {
            char c = tcpClient.read();
            if (c == '\n')
            {
                if (tcp_buffer_idx > 0)
                {
                    tcp_command_buffer[tcp_buffer_idx] = '\0';
                    parseAndExecuteTCPCommand(String(tcp_command_buffer));
                    tcp_buffer_idx = 0;
                }
            }
            else if (c >= 32)
            {
                tcp_command_buffer[tcp_buffer_idx++] = c;
            }
        }
    }
    else if (tcp_connected)
    {
        Serial.println("TCP client disconnected");
        tcp_connected = false;
        tcpClient.stop();

        if (mode_lock == AUTO_MODE)
        {
            control_mode = WEB_MODE;
        }
        status_changed = true;
    }
}

void parseAndExecuteTCPCommand(String command)
{
    command.trim();
    if (command.length() == 0) return;

    Serial.print("TCP command: ");
    Serial.println(command);

    last_tcp_command = millis();

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

// ==================== Actuator Update ====================
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
