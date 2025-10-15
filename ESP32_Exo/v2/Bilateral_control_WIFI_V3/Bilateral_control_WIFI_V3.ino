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
// WiFi AP Configuration (for web control)
const char *ap_ssid = "ESP32_Glove";
const char *ap_password = "12345678";

// WiFi STA Configuration (connect to computer WiFi)
const char *sta_ssid = WIFI_STA_SSID;
const char *sta_password = WIFI_STA_PASSWORD;

// TCP Configuration
const int tcp_port = 4210;

// ==================== Hardware Configuration ====================
// Finger control pins
const int flexion_pins[5] = {13, 14, 12, 27, 15};  // Flexion control pins
const int extension_pins[5] = {17, 5, 18, 19, 15}; // Extension control pins
const int pinching_pins[5] = {15, 15, 15, 15, 15}; // Pinching control pins
const int abduction_pin = 15;                      // Abduction pin
const int adduction_pin = 16;                      // Adduction pin
const int emergency_pin = 15;                      // Emergency stop pin
// Remote button bridge configuration
const bool button_bridge_serial_enabled = true;
const int button_serial_rx_pin = 35;                        // RX pin for secondary board UART (input only)
const int button_serial_tx_pin = 4;                         // TX pin (optional acknowledge channel)
const unsigned long button_bridge_activity_timeout = 10000; // 10 second activity window

const bool button_bridge_wifi_enabled = true;
const unsigned int button_udp_port = 4211; // UDP port for remote button packets

// I2C Configuration
const int sda_pin = 21;
const int scl_pin = 22;

// ==================== Global Variables ====================
// Control modes
enum ControlMode
{
    WEB_MODE,
    TCP_MODE,
    BUTTON_MODE
};
ControlMode control_mode = WEB_MODE;

// Control mode lock settings
enum ControlModeLock
{
    AUTO_MODE,        // Automatic switching based on TCP connection
    FORCE_WEB_MODE,   // Always stay in WEB mode
    FORCE_TCP_MODE,   // Always stay in TCP mode
    FORCE_BUTTON_MODE // Always stay in BUTTON mode
};
ControlModeLock mode_lock = AUTO_MODE;

// Gesture and states
int gesture = 0;                 // Gesture (0-8)
int pressure[2] = {50, 50};      // Pressure [flexion, extension] (0-100)
int speed = 1;                   // Speed (0-4)
String finger_states = "000000"; // Finger states string

// Data-driven gesture mapping for easier modification
const char *GESTURE_TO_FINGER_STATES_MAP[] = {
    "000000", // 0: Relax
    "111111", // 1: All flex (HandClose)
    "222220", // 2: All extend (HandOpen)
    "011110", // 3: IMRP Flexion (HookGrasp)
    "111110", // 4: 3-finger pinch (LateralGrasp)
    "100000", // 5: Thumb
    "010000", // 6: Index
    "001110", // 7: Middle, Ring, Pinky
    "121110"  // 8: Index Pointing
};
const int NUM_GESTURES = sizeof(GESTURE_TO_FINGER_STATES_MAP) / sizeof(GESTURE_TO_FINGER_STATES_MAP[0]);

// Hardware objects
WebServer server(80);
WiFiServer tcpServer(tcp_port);
WiFiClient tcpClient;
Adafruit_MCP4728 dac;
bool dac_available = false;

// Network status
bool tcp_connected = false;
bool tcp_server_started = false; // Flag to track server status
unsigned long last_tcp_command = 0;
const unsigned long tcp_timeout = 20000; // 5 second timeout
char tcp_command_buffer[256];            // Buffer for incoming TCP commands
int tcp_buffer_idx = 0;

// Status update flags
bool status_changed = true;

// Button control variables
unsigned long last_button_press = 0;
const unsigned long button_debounce_delay = 200; // 200ms debounce
int button_primary_gesture = 1;                  // First gesture in the press cycle
int button_secondary_gesture = 2;                // Second gesture when using three-press cycle
bool button_use_three_press_cycle = false;
int button_cycle_state = 0;         // 0 = rest, 1 = primary, 2 = secondary
bool button_gesture_active = false; // Track if button gesture is active

// Remote button bridge state
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
        h1 { color: #333; margin-bottom: 30px; }
        .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .section h3 { margin-top: 0; color: #666; }
        .button-group { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin: 15px 0; }
        button { padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; transition: all 0.3s; }
        .btn-primary { background: #007bff; color: white; }
        .btn-primary:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-secondary:hover { background: #545b62; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .control-row { display: flex; align-items: center; justify-content: space-between; margin: 10px 0; }
        input[type="number"] { width: 80px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; text-align: center; }
        .status { margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; font-family: monospace; border-left: 4px solid #007bff; }
        .mode-indicator { padding: 8px 16px; border-radius: 20px; color: white; font-weight: bold; display: inline-block; }
        .mode-web { background: #28a745; }
        .mode-tcp { background: #17a2b8; }
        .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }
        .status-item { background: #e9ecef; padding: 10px; border-radius: 5px; }
        .status-value { font-weight: bold; color: #007bff; font-size: 18px; }
        .connection-status { display: flex; align-items: center; gap: 10px; }
        .status-dot { width: 12px; height: 12px; border-radius: 50%; }
        .status-online { background: #28a745; }
        .status-offline { background: #dc3545; }
        .realtime-display { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .gesture-display { font-size: 24px; font-weight: bold; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ESP32 Glove Control System</h1>
        
        <div class="section">
            <h3>System Status</h3>
            <div id="mode-status" class="mode-indicator mode-web">Web Control Mode</div>
            <div class="status">
                <div class="connection-status">
                    <span>WiFi AP:</span>
                    <div class="status-dot status-online"></div>
                    <span>ESP32_Glove (192.168.4.1)</span>
                </div>
                <div class="connection-status">
                    <span>WiFi STA:</span>
                    <div id="sta-dot" class="status-dot status-offline"></div>
                    <span id="sta-status">Connecting...</span>
                </div>
                <div class="connection-status">
                    <span>TCP Client:</span>
                    <div id="tcp-dot" class="status-dot status-offline"></div>
                    <span id="tcp-status">Waiting...</span>
                </div>
                <div class="connection-status">
                    <span>Button Bridge:</span>
                    <div id="button-bridge-dot" class="status-dot status-offline"></div>
                    <span id="button-bridge-status">Waiting for activity...</span>
                </div>
            </div>
        </div>

        <div class="realtime-display">
            <h3 style="margin-top: 0;">Real-time Status</h3>
            <div class="gesture-display">Current Gesture: <span id="current-gesture">Relax</span></div>
            <div class="status-grid">
                <div class="status-item">
                    <div>Flexion Pressure</div>
                    <div class="status-value"><span id="current-flex">50</span>%</div>
                </div>
                <div class="status-item">
                    <div>Extension Pressure</div>
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
            <div class="status-grid">
                <div class="status-item">
                    <div>Current Mode</div>
                    <div class="status-value"><span id="current-mode">WEB</span></div>
                </div>
                <div class="status-item">
                    <div>Mode Lock</div>
                    <div class="status-value"><span id="mode-lock-status">AUTO</span></div>
                </div>
            </div>
            <div class="button-group">
                <button class="btn-secondary" onclick="setControlMode('WEB')">Force WEB Mode</button>
                <button class="btn-secondary" onclick="setControlMode('TCP')">Force TCP Mode</button>
                <button class="btn-secondary" onclick="setControlMode('BUTTON')">Force BUTTON Mode</button>
                <button class="btn-primary" onclick="setControlMode('AUTO')">Auto Mode</button>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: #666;">
                <strong>AUTO:</strong> Mode switches automatically when TCP client connects<br>
                <strong>FORCE:</strong> Mode stays locked regardless of connections<br>
                <strong>BUTTON:</strong> Push button toggles between gesture and relax state
            </div>
        </div>

        <div class="section" id="button-mode-config" style="display:none;">
            <h3>Button Mode Configuration</h3>
            <div class="control-row">
                <label>Primary Gesture:</label>
                <select id="button-primary-select" onchange="setButtonPrimaryGesture()">
                    <option value="1">HandClose</option>
                    <option value="2">HandOpen</option>
                    <option value="3">HookGrasp</option>
                    <option value="4">LateralGrasp</option>
                    <option value="5">ThumbFlexion</option>
                    <option value="6">IndexFlexion</option>
                    <option value="7">MRPFlexion</option>
                    <option value="8">IndexPointing</option>
                </select>
            </div>
            <div class="control-row">
                <label>Secondary Gesture:</label>
                <select id="button-secondary-select" onchange="setButtonSecondaryGesture()">
                    <option value="1">HandClose</option>
                    <option value="2">HandOpen</option>
                    <option value="3">HookGrasp</option>
                    <option value="4">LateralGrasp</option>
                    <option value="5">ThumbFlexion</option>
                    <option value="6">IndexFlexion</option>
                    <option value="7">MRPFlexion</option>
                    <option value="8">IndexPointing</option>
                </select>
            </div>
            <div class="control-row">
                <label>Cycle Mode:</label>
                <select id="button-cycle-mode" onchange="setButtonCycleMode()">
                    <option value="2">2-press (Primary → Rest)</option>
                    <option value="3">3-press (Primary → Secondary → Rest)</option>
                </select>
            </div>
            <div class="control-row" style="justify-content: flex-start; gap: 10px;">
                <div>Current Cycle State:</div>
                <div class="status-value" id="button-cycle-state-label">Rest</div>
                <button class="btn-secondary" onclick="resetButtonCycle()">Reset</button>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: #666;">
                Configure how many presses rotate through the primary and secondary gestures before returning to rest.
            </div>
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
                <button class="btn-primary" onclick="setGesture(5)">ThumbFlexion</button>
                <button class="btn-primary" onclick="setGesture(6)">IndexFlexion</button>
                <button class="btn-primary" onclick="setGesture(7)">MRPFlexion</button>
                <button class="btn-primary" onclick="setGesture(8)">IndexPointing</button>
            </div>
        </div>

        <div class="section">
            <h3>Manual Control</h3>
            <div class="control-row">
                <label>Flexion Pressure (0-100):</label>
                <input type="number" id="flex-pressure" min="0" max="100" value="50">
                <button class="btn-secondary" onclick="setPressure()">Set</button>
            </div>
            <div class="control-row">
                <label>Extension Pressure (0-100):</label>
                <input type="number" id="ext-pressure" min="0" max="100" value="50">
            </div>
            <div class="control-row">
                <label>Speed Level (0-4):</label>
                <input type="number" id="speed-level" min="0" max="4" value="1">
                <button class="btn-secondary" onclick="setSpeed()">Set</button>
            </div>
            <div class="control-row">
                <label>Finger States (6 digits):</label>
                <input type="text" id="finger-states" maxlength="6" value="000000" style="width: 120px;">
                <button class="btn-secondary" onclick="setFingerStates()">Set</button>
            </div>
        </div>

        <div class="section">
            <h3>Emergency Controls</h3>
            <button class="btn-danger" onclick="emergencyStop()" style="font-size: 16px; padding: 15px 30px;">EMERGENCY STOP</button>
        </div>

        <div class="section">
            <h3>TCP Connection Info</h3>
            <div class="status">
                <div>TCP Server Port: 4210</div>
                <div>AP Mode: <strong>192.168.4.1:4210</strong></div>
                <div>STA Mode: <strong>Check status above for IP:4210</strong></div>
                <div>Commands: g:X (gesture), p:X:Y (pressure), s:X (speed), f:XXXXXX (fingers), stop</div>
                <div>Example: "g:1" sets gesture to HandClose, "p:75:25" sets flex:75% ext:25%</div>
                <button class="btn-secondary" onclick="testTcpServer()" style="margin-top: 10px;">Test TCP Server Status</button>
                <div id="tcp-test-result" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; display: none;"></div>
            </div>
        </div>
    </div>

    <script>
        const gestureNames = ["Relax", "HandClose", "HandOpen", "HookGrasp", "LateralGrasp", "ThumbFlexion", "IndexFlexion", "MRPFlexion", "IndexPointing"];
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // Update mode indicator
                    const modeElement = document.getElementById('mode-status');
                    if (data.mode === 'TCP') {
                        modeElement.className = 'mode-indicator mode-tcp';
                        modeElement.textContent = 'TCP Control Mode (Computer Connected)';
                    } else if (data.mode === 'BUTTON') {
                        modeElement.className = 'mode-indicator mode-web';
                        modeElement.textContent = 'Button Control Mode';
                    } else {
                        modeElement.className = 'mode-indicator mode-web';
                        modeElement.textContent = 'Web Control Mode';
                    }
                    
                    // Show/hide button mode configuration
                    const buttonModeConfig = document.getElementById('button-mode-config');
                    if (data.mode === 'BUTTON') {
                        buttonModeConfig.style.display = 'block';
                    } else {
                        buttonModeConfig.style.display = 'none';
                    }
                    
                    // Update connection status
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
                        tcpStatus.textContent = 'Connected from ' + data.tcp_client_ip;
                    } else {
                        tcpDot.className = 'status-dot status-offline';
                        tcpStatus.textContent = 'Waiting for connection...';
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
                            let statusText = channels.join(' + ');
                            if (typeof data.button_bridge.last_ms === 'number' && data.button_bridge.last_ms >= 0) {
                                const secondsAgo = Math.round(data.button_bridge.last_ms / 1000);
                                const sourceLabelMap = { SERIAL: 'Serial', UDP: 'WiFi' };
                                const sourceLabel = sourceLabelMap[data.button_bridge.last_source] || data.button_bridge.last_source || 'unknown';
                                statusText += ' • last ' + sourceLabel + ' ' + secondsAgo + 's ago';
                            }
                            buttonBridgeStatus.textContent = statusText;
                        } else {
                            buttonBridgeStatus.textContent = 'No activity';
                        }
                    } else {
                        buttonBridgeDot.className = 'status-dot status-offline';
                        buttonBridgeStatus.textContent = 'Unavailable';
                    }
                    
                    // Update real-time status
                    document.getElementById('current-gesture').textContent = gestureNames[data.gesture] || 'Unknown';
                    document.getElementById('current-flex').textContent = data.pressure[0];
                    document.getElementById('current-ext').textContent = data.pressure[1];
                    document.getElementById('current-speed').textContent = data.speed;
                    document.getElementById('current-fingers').textContent = data.finger_states;
                    
                    // Update control mode status
                    document.getElementById('current-mode').textContent = data.mode;
                    document.getElementById('mode-lock-status').textContent = data.mode_lock;
                    
                    // Update input fields with current values
                    document.getElementById('flex-pressure').value = data.pressure[0];
                    document.getElementById('ext-pressure').value = data.pressure[1];
                    document.getElementById('speed-level').value = data.speed;
                    document.getElementById('finger-states').value = data.finger_states;

                    if (data.button_config) {
                        const config = data.button_config;
                        const primarySelect = document.getElementById('button-primary-select');
                        const secondarySelect = document.getElementById('button-secondary-select');
                        const cycleModeSelect = document.getElementById('button-cycle-mode');
                        const cycleStateLabel = document.getElementById('button-cycle-state-label');

                        if (primarySelect) primarySelect.value = String(config.primary);
                        if (secondarySelect) secondarySelect.value = String(config.secondary);
                        if (cycleModeSelect) cycleModeSelect.value = config.use_three_press ? '3' : '2';
                        if (secondarySelect) secondarySelect.disabled = !config.use_three_press;

                        if (cycleStateLabel) {
                            let label = 'Rest';
                            if (config.cycle_state === 1) {
                                label = 'Primary: ' + (gestureNames[config.primary] || 'Gesture ' + config.primary);
                            } else if (config.cycle_state === 2 && config.use_three_press) {
                                label = 'Secondary: ' + (gestureNames[config.secondary] || 'Gesture ' + config.secondary);
                            }
                            cycleStateLabel.textContent = label;
                        }
                    }
                })
                .catch(error => console.log('Status update failed:', error));
        }

        function sendCommand(endpoint, params = '') {
            const url = params ? `/${endpoint}?${params}` : `/${endpoint}`;
            fetch(url)
                .then(response => response.text())
                .then(result => {
                    if (result !== 'OK') {
                        console.log('Command result:', result);
                    }
                })
                .catch(error => console.log('Command failed:', error));
        }

        function setGesture(g) {
            sendCommand('gesture', `value=${g}`);
        }

        function setPressure() {
            const flex = document.getElementById('flex-pressure').value;
            const ext = document.getElementById('ext-pressure').value;
            sendCommand('pressure', `flex=${flex}&ext=${ext}`);
        }

        function setSpeed() {
            const speed = document.getElementById('speed-level').value;
            sendCommand('speed', `value=${speed}`);
        }

        function setFingerStates() {
            const states = document.getElementById('finger-states').value;
            if (states.length === 6 && /^[0-3]+$/.test(states)) {
                sendCommand('fingers', `value=${states}`);
            } else {
                alert('Finger states must be 6 digits (0-3)');
            }
        }

        function emergencyStop() {
            sendCommand('stop');
        }

        function setControlMode(mode) {
            sendCommand('mode', `value=${mode}`);
            // Force immediate status update to reflect changes
            setTimeout(updateStatus, 200);
            
            // Show/hide button mode configuration
            const buttonModeConfig = document.getElementById('button-mode-config');
            if (mode === 'BUTTON') {
                buttonModeConfig.style.display = 'block';
            } else {
                buttonModeConfig.style.display = 'none';
            }
        }

        function setButtonPrimaryGesture() {
            const gesture = document.getElementById('button-primary-select').value;
            sendCommand('button-gesture', `value=${gesture}`);
        }

        function setButtonSecondaryGesture() {
            const gesture = document.getElementById('button-secondary-select').value;
            sendCommand('button-secondary-gesture', `value=${gesture}`);
        }

        function setButtonCycleMode() {
            const mode = document.getElementById('button-cycle-mode').value;
            sendCommand('button-cycle-mode', `value=${mode}`);
            const secondarySelect = document.getElementById('button-secondary-select');
            if (secondarySelect) {
                secondarySelect.disabled = (mode !== '3');
            }
        }

        function resetButtonCycle() {
            sendCommand('button-cycle-reset');
        }

        function testTcpServer() {
            fetch('/tcp-test')
                .then(response => response.text())
                .then(result => {
                    const resultDiv = document.getElementById('tcp-test-result');
                    resultDiv.innerHTML = '<pre>' + result + '</pre>';
                    resultDiv.style.display = 'block';
                })
                .catch(error => {
                    const resultDiv = document.getElementById('tcp-test-result');
                    resultDiv.innerHTML = 'Error testing TCP server: ' + error;
                    resultDiv.style.display = 'block';
                });
        }

        // Auto update status every 1 second
        setInterval(updateStatus, 1000);
        updateStatus();
        
        // Initial setup
        window.onload = function() {
            console.log('ESP32 Glove Control System Ready');
        }
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
void toggleButtonGesture(const char *source);
void setButtonGestureActive(bool active, const char *source);
void advanceButtonCycle(const char *source);
void setButtonCycleState(int state, const char *source);
void applyButtonCycleState(const char *source);
int sanitizeGestureId(int gestureId);
bool extractButtonCommandValue(const String &normalized, int &value);
void updateActuators();
void gestureToFingerStates();
void setFingerStates();
void setPressureDAC();
void setSpeedDAC();
void parseAndExecuteTCPCommand(String command);

// ==================== Main Program ====================
/**
 * @brief Initializes the system on startup.
 */
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
    // Check emergency stop
    if (digitalRead(emergency_pin) == LOW)
    {
        emergencyStop();
        delay(100);
        return;
    }

    // Handle web requests
    server.handleClient();

    // Handle TCP commands
    handleTCPCommands();

    // Handle button control
    handleButtonControl();

    // Periodic TCP server status check (every 30 seconds)
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

    // Check TCP connection timeout
    if (tcp_connected && (millis() - last_tcp_command > tcp_timeout))
    {
        Serial.println("TCP connection timeout, switching to Web mode");
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    // Also check if TCP client is still connected
    if (tcp_connected && !tcpClient.connected())
    {
        Serial.println("TCP client disconnected (connection check), switching to Web mode");
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    // Update actuators
    updateActuators();

    delay(10);
}

// ==================== Hardware Initialization ====================
void initHardware()
{
    Serial.println("Initializing hardware...");

    // Set all control pins as output and set to LOW
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
    else
    {
        Serial.println("  Serial bridge disabled");
    }

    if (button_bridge_wifi_enabled)
    {
        button_udp_initialized = button_udp.begin(button_udp_port);
        if (button_udp_initialized)
        {
            Serial.print("  UDP bridge listening on port ");
            Serial.println(button_udp_port);
        }
        else
        {
            Serial.println("  UDP bridge failed to start");
        }
    }
    else
    {
        Serial.println("  UDP bridge disabled");
    }

    Serial.println("Remote button bridge ready");
}

void pollButtonBridgeInterfaces()
{
    // Serial interface polling
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

    // UDP interface polling
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

    // Expire activity state when idle
    unsigned long now = millis();
    if (button_bridge_serial_enabled && last_button_bridge_serial_activity > 0 && now - last_button_bridge_serial_activity > button_bridge_activity_timeout)
    {
        last_button_bridge_serial_activity = 0;
    }
    if (button_bridge_wifi_enabled && last_button_bridge_wifi_activity > 0 && now - last_button_bridge_wifi_activity > button_bridge_activity_timeout)
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
    if (delimiterIndex < 0)
    {
        delimiterIndex = normalized.indexOf('=');
    }
    if (delimiterIndex < 0)
    {
        delimiterIndex = normalized.indexOf(' ');
    }

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
    if (command.length() == 0)
    {
        return;
    }

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
        toggleButtonGesture(source);
    }
    else if (normalized == "ON")
    {
        recognized = true;
        setButtonGestureActive(true, source);
    }
    else if (normalized == "OFF" || normalized == "RELEASE")
    {
        recognized = true;
        setButtonGestureActive(false, source);
    }
    else if (normalized.startsWith("GESTURE"))
    {
        recognized = true;
        int requestedGesture = -1;
        if (extractButtonCommandValue(normalized, requestedGesture))
        {
            if (requestedGesture >= 1 && requestedGesture < NUM_GESTURES)
            {
                button_primary_gesture = requestedGesture;
                Serial.printf("[BUTTON][%s] Primary gesture set to %d\n", source, button_primary_gesture);
                if (control_mode == BUTTON_MODE && button_cycle_state == 1)
                {
                    applyButtonCycleState(source);
                }
            }
            else
            {
                Serial.printf("[BUTTON][%s] Invalid gesture value: %d\n", source, requestedGesture);
            }
        }
        else
        {
            Serial.printf("[BUTTON][%s] Malformed gesture command: %s\n", source, command.c_str());
        }
    }
    else if (normalized.startsWith("PRIMARY"))
    {
        recognized = true;
        int requestedGesture = -1;
        if (extractButtonCommandValue(normalized, requestedGesture))
        {
            if (requestedGesture >= 1 && requestedGesture < NUM_GESTURES)
            {
                button_primary_gesture = requestedGesture;
                Serial.printf("[BUTTON][%s] Primary gesture set to %d\n", source, button_primary_gesture);
                if (control_mode == BUTTON_MODE && button_cycle_state == 1)
                {
                    applyButtonCycleState(source);
                }
            }
            else
            {
                Serial.printf("[BUTTON][%s] Invalid primary gesture: %d\n", source, requestedGesture);
            }
        }
        else
        {
            Serial.printf("[BUTTON][%s] Malformed primary command: %s\n", source, command.c_str());
        }
    }
    else if (normalized.startsWith("SECONDARY"))
    {
        recognized = true;
        int requestedGesture = -1;
        if (extractButtonCommandValue(normalized, requestedGesture))
        {
            if (requestedGesture >= 1 && requestedGesture < NUM_GESTURES)
            {
                button_secondary_gesture = requestedGesture;
                Serial.printf("[BUTTON][%s] Secondary gesture set to %d\n", source, button_secondary_gesture);
                if (control_mode == BUTTON_MODE && button_cycle_state == 2)
                {
                    applyButtonCycleState(source);
                }
            }
            else
            {
                Serial.printf("[BUTTON][%s] Invalid secondary gesture: %d\n", source, requestedGesture);
            }
        }
        else
        {
            Serial.printf("[BUTTON][%s] Malformed secondary command: %s\n", source, command.c_str());
        }
    }
    else if (normalized.startsWith("CYCLE"))
    {
        recognized = true;
        int cycleValue = -1;
        if (extractButtonCommandValue(normalized, cycleValue))
        {
            bool useThreePress = cycleValue >= 3;
            button_use_three_press_cycle = useThreePress;
            Serial.printf("[BUTTON][%s] Cycle mode set to %s-press\n", source, useThreePress ? "three" : "two");
            if (!button_use_three_press_cycle && button_cycle_state == 2)
            {
                setButtonCycleState(0, source);
            }
        }
        else
        {
            Serial.printf("[BUTTON][%s] Malformed cycle command: %s\n", source, command.c_str());
        }
    }
    else if (normalized == "RESET")
    {
        recognized = true;
        setButtonCycleState(0, source);
    }

    if (recognized)
    {
        status_changed = true;
    }
    else
    {
        Serial.printf("[BUTTON][%s] Unrecognized command: %s\n", source, command.c_str());
    }
}

void toggleButtonGesture(const char *source)
{
    if (control_mode != BUTTON_MODE)
    {
        Serial.printf("[BUTTON][%s] Command ignored - not in BUTTON mode\n", source);
        return;
    }

    unsigned long now = millis();
    if (now - last_button_press < button_debounce_delay)
    {
        return;
    }

    last_button_press = now;

    advanceButtonCycle(source);
}

void setButtonGestureActive(bool active, const char *source)
{
    if (control_mode != BUTTON_MODE)
    {
        Serial.printf("[BUTTON][%s] Command ignored - not in BUTTON mode\n", source);
        return;
    }

    unsigned long now = millis();
    bool isCurrentlyInTargetState = active ? (button_cycle_state == 1) : (button_cycle_state == 0);
    if (now - last_button_press < button_debounce_delay && isCurrentlyInTargetState)
    {
        return;
    }

    if (active)
    {
        last_button_press = now;
        setButtonCycleState(1, source);
    }
    else
    {
        last_button_press = now;
        setButtonCycleState(0, source);
    }
}

void advanceButtonCycle(const char *source)
{
    int nextState = 0;
    if (button_use_three_press_cycle)
    {
        if (button_cycle_state == 0)
        {
            nextState = 1;
        }
        else if (button_cycle_state == 1)
        {
            nextState = 2;
        }
        else
        {
            nextState = 0;
        }
    }
    else
    {
        nextState = (button_cycle_state == 0) ? 1 : 0;
    }

    setButtonCycleState(nextState, source);
}

void setButtonCycleState(int state, const char *source)
{
    int sanitizedState = state;
    if (button_use_three_press_cycle)
    {
        sanitizedState = constrain(sanitizedState, 0, 2);
    }
    else
    {
        sanitizedState = sanitizedState > 0 ? 1 : 0;
    }

    if (sanitizedState != button_cycle_state)
    {
        button_cycle_state = sanitizedState;
    }

    applyButtonCycleState(source);
    status_changed = true;
}

void applyButtonCycleState(const char *source)
{
    int desiredGesture = 0;
    bool desiredActive = false;

    if (button_cycle_state == 1)
    {
        desiredGesture = sanitizeGestureId(button_primary_gesture);
        desiredActive = true;
    }
    else if (button_cycle_state == 2 && button_use_three_press_cycle)
    {
        desiredGesture = sanitizeGestureId(button_secondary_gesture);
        desiredActive = true;
    }

    bool inButtonMode = (control_mode == BUTTON_MODE);
    bool gestureChanged = inButtonMode && gesture != desiredGesture;
    bool activeChanged = button_gesture_active != desiredActive;

    if (inButtonMode)
    {
        gesture = desiredGesture;
    }

    button_gesture_active = desiredActive;

    if (gestureChanged || activeChanged)
    {
        if (inButtonMode)
        {
            if (button_gesture_active)
            {
                Serial.printf("[BUTTON][%s] Gesture ON - Gesture %d (cycle state %d)\n", source, gesture, button_cycle_state);
            }
            else
            {
                Serial.printf("[BUTTON][%s] Gesture OFF - Relax state\n", source);
            }
        }
        status_changed = true;
    }
}

int sanitizeGestureId(int gestureId)
{
    return constrain(gestureId, 1, NUM_GESTURES - 1);
}

// ==================== Button Control Handler ====================
void handleButtonControl()
{
    pollButtonBridgeInterfaces();
}

// ==================== Network Initialization ====================
void initNetworks()
{
    Serial.println("Initializing networks...");

    // Start AP mode (web control)
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(ap_ssid, ap_password);
    Serial.print("AP started: ");
    Serial.println(WiFi.softAPIP());

    // Connect to STA network (TCP control)
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
        Serial.print("TCP server will be available at: ");
        Serial.print(WiFi.localIP());
        Serial.print(":");
        Serial.println(tcp_port);
    }
    else
    {
        Serial.println("\nSTA connection failed, AP only mode");
        Serial.print("TCP server will be available at AP IP: ");
        Serial.print(WiFi.softAPIP());
        Serial.print(":");
        Serial.println(tcp_port);
    }

    // Start TCP server with retry mechanism
    for (int attempts = 0; attempts < 3; attempts++)
    {
        tcpServer.begin();
        delay(100);

        // Try to verify the server is listening by checking for incoming connections
        Serial.print("TCP server start attempt ");
        Serial.print(attempts + 1);
        Serial.print("/3 on port ");
        Serial.println(tcp_port);

        tcp_server_started = true; // Assume success for now
        break;                     // WiFiServer.begin() doesn't return status, so we assume success
    }

    if (tcp_server_started)
    {
        tcpServer.setNoDelay(true); // Disable Nagle algorithm for faster response
        Serial.println("✓ TCP server successfully started");
    }
    else
    {
        Serial.println("✗ TCP server failed to start");
    }

    // Print available connection endpoints
    Serial.println("TCP server endpoints:");
    Serial.print("  AP Mode: ");
    Serial.print(WiFi.softAPIP());
    Serial.print(":");
    Serial.println(tcp_port);

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.print("  STA Mode: ");
        Serial.print(WiFi.localIP());
        Serial.print(":");
        Serial.println(tcp_port);
        Serial.println("  Use this IP for nmap scanning from external devices");
    }
    else
    {
        Serial.println("  STA Mode: Not connected - use AP mode IP for testing");
    }

    // Setup web server routes
    server.on("/", []()
              { server.send(200, "text/html", html_page); });

    server.on("/status", []()
              {
        StaticJsonDocument<768> json_doc;
        char json_buffer[768];

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

        bool serialActive = button_bridge_serial_enabled && last_button_bridge_serial_activity > 0 && (millis() - last_button_bridge_serial_activity) <= button_bridge_activity_timeout;
        bool wifiActive = button_bridge_wifi_enabled && last_button_bridge_wifi_activity > 0 && (millis() - last_button_bridge_wifi_activity) <= button_bridge_activity_timeout;

        JsonObject buttonBridge = json_doc.createNestedObject("button_bridge");
        buttonBridge["serial_active"] = serialActive;
        buttonBridge["wifi_active"] = wifiActive;
        buttonBridge["last_source"] = last_button_bridge_source;
        buttonBridge["last_ms"] = (last_button_bridge_activity > 0) ? (millis() - last_button_bridge_activity) : -1;

    JsonObject buttonConfig = json_doc.createNestedObject("button_config");
    buttonConfig["primary"] = button_primary_gesture;
    buttonConfig["secondary"] = button_secondary_gesture;
    buttonConfig["use_three_press"] = button_use_three_press_cycle;
    buttonConfig["cycle_state"] = button_cycle_state;
    buttonConfig["active"] = button_gesture_active;

        serializeJson(json_doc, json_buffer);
        server.send(200, "application/json", json_buffer); });

    server.on("/gesture", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            gesture = server.arg("value").toInt();
            if (gesture < 0 || gesture > 8) gesture = 0;
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
                // Disconnect TCP client if connected
                if (tcp_connected) {
                    tcpClient.stop();
                    tcp_connected = false;
                }
                setButtonCycleState(0, "WEB");
                Serial.println("Web: Control mode forced to WEB");
            }
            else if (mode == "TCP") {
                mode_lock = FORCE_TCP_MODE;
                control_mode = TCP_MODE;
                setButtonCycleState(0, "WEB");
                Serial.println("Web: Control mode forced to TCP");
            }
            else if (mode == "BUTTON") {
                mode_lock = FORCE_BUTTON_MODE;
                control_mode = BUTTON_MODE;
                // Disconnect TCP client if connected
                if (tcp_connected) {
                    tcpClient.stop();
                    tcp_connected = false;
                }
                // Reset button gesture state when entering button mode
                setButtonCycleState(0, "WEB");
                applyButtonCycleState("WEB");
                Serial.println("Web: Control mode forced to BUTTON");
            }
            else if (mode == "AUTO") {
                mode_lock = AUTO_MODE;
                // Let the system decide mode based on current TCP connection
                control_mode = tcp_connected ? TCP_MODE : WEB_MODE;
                if (control_mode != BUTTON_MODE) {
                    setButtonCycleState(0, "WEB");
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

    server.on("/button-gesture", []()
              {
        if (server.hasArg("value")) {
            int requested = server.arg("value").toInt();
            if (requested >= 1 && requested < NUM_GESTURES) {
                button_primary_gesture = requested;
                Serial.print("Web: Button primary gesture set to ");
                Serial.println(button_primary_gesture);
                if (control_mode == BUTTON_MODE && button_cycle_state == 1) {
                    applyButtonCycleState("WEB");
                }
                status_changed = true;
            }
            else {
                Serial.print("Web: Invalid button primary gesture: ");
                Serial.println(requested);
            }
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/button-secondary-gesture", []()
              {
        if (server.hasArg("value")) {
            int requested = server.arg("value").toInt();
            if (requested >= 1 && requested < NUM_GESTURES) {
                button_secondary_gesture = requested;
                Serial.print("Web: Button secondary gesture set to ");
                Serial.println(button_secondary_gesture);
                if (control_mode == BUTTON_MODE && button_cycle_state == 2) {
                    applyButtonCycleState("WEB");
                }
                status_changed = true;
            }
            else {
                Serial.print("Web: Invalid button secondary gesture: ");
                Serial.println(requested);
            }
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/button-cycle-mode", []()
              {
        if (server.hasArg("value")) {
            String cycleMode = server.arg("value");
            cycleMode.trim();
            cycleMode.toUpperCase();

            bool useThreePress = (cycleMode == "3" || cycleMode == "THREE" || cycleMode == "3PRESS" || cycleMode == "THREE_PRESS");
            button_use_three_press_cycle = useThreePress;
            Serial.print("Web: Button cycle mode set to ");
            Serial.println(useThreePress ? "three-press" : "two-press");
            if (!button_use_three_press_cycle && button_cycle_state == 2) {
                setButtonCycleState(0, "WEB");
            }
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/button-cycle-reset", []()
              {
        setButtonCycleState(0, "WEB");
        status_changed = true;
        server.send(200, "text/plain", "OK"); });

    server.on("/tcp-test", []()
              {
        String response = "TCP Server Status:\n";
        response += "Port: " + String(tcp_port) + "\n";
        response += "Server Started: " + String(tcp_server_started ? "YES" : "NO") + "\n";
        response += "Client Connected: " + String(tcp_connected ? "YES" : "NO") + "\n";
        if (WiFi.status() == WL_CONNECTED) {
            response += "STA IP: " + WiFi.localIP().toString() + ":" + String(tcp_port) + "\n";
        }
        response += "AP IP: " + WiFi.softAPIP().toString() + ":" + String(tcp_port) + "\n";
        server.send(200, "text/plain", response); });

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
        Serial.println("DAC initialization failed - using digital control only");
    }
}

// ==================== TCP Command Handler ====================
void handleTCPCommands()
{
    // Check for new TCP client connections
    if (!tcp_connected && tcpServer.hasClient())
    {
        // Only accept TCP connections if not forced to WEB mode
        if (mode_lock != FORCE_WEB_MODE)
        {
            // Close any existing connection first to be safe
            if (tcpClient)
            {
                tcpClient.stop();
            }

            tcpClient = tcpServer.available();
            if (tcpClient)
            {
                tcp_connected = true;
                if (mode_lock == AUTO_MODE)
                {
                    control_mode = TCP_MODE;
                }
                tcp_buffer_idx = 0; // Reset buffer for new client
                Serial.print("TCP client connected from: ");
                Serial.println(tcpClient.remoteIP());

                // Send welcome message
                tcpClient.println("ESP32 Glove Control Ready");
                tcpClient.flush();

                last_tcp_command = millis();
                status_changed = true;
            }
        }
        else
        {
            // Reject TCP connection when forced to WEB mode
            WiFiClient rejectClient = tcpServer.available();
            if (rejectClient)
            {
                rejectClient.println("ERROR: ESP32 forced to WEB mode, TCP disabled");
                rejectClient.stop();
                Serial.println("TCP connection rejected - ESP32 forced to WEB mode");
            }
        }
    }

    // Handle existing TCP client
    if (tcp_connected && tcpClient.connected())
    {
        while (tcpClient.available() && tcp_buffer_idx < sizeof(tcp_command_buffer) - 1)
        {
            char c = tcpClient.read();
            if (c == '\n')
            { // Command terminated by newline
                if (tcp_buffer_idx > 0)
                {
                    tcp_command_buffer[tcp_buffer_idx] = '\0'; // Null-terminate the string
                    parseAndExecuteTCPCommand(String(tcp_command_buffer));
                    tcp_buffer_idx = 0; // Reset buffer
                }
            }
            else if (c >= 32)
            { // Ignore other control characters
                tcp_command_buffer[tcp_buffer_idx++] = c;
            }
        }
    }
    else if (tcp_connected)
    {
        // Client disconnected or connection lost
        Serial.println("TCP client disconnected");
        tcp_connected = false;
        tcpClient.stop();

        // Only switch to WEB mode if not forced to TCP mode
        if (mode_lock == AUTO_MODE)
        {
            control_mode = WEB_MODE;
            Serial.println("Switching to Web mode (AUTO mode)");
        }
        else if (mode_lock == FORCE_TCP_MODE)
        {
            control_mode = TCP_MODE;
            Serial.println("Staying in TCP mode (FORCE_TCP mode)");
        }
        // FORCE_WEB_MODE already handles this in connection logic

        status_changed = true;
    }
}

/**
 * @brief Parses a command string from TCP and executes it.
 * @param command The command string to parse.
 */
void parseAndExecuteTCPCommand(String command)
{
    command.trim();
    if (command.length() == 0)
        return;

    Serial.print("TCP command: ");
    Serial.println(command);

    last_tcp_command = millis();

    // Parse and execute command
    int colonIndex = command.indexOf(':');
    if (colonIndex > 0)
    {
        String cmdType = command.substring(0, colonIndex);
        String params = command.substring(colonIndex + 1);

        if (cmdType == "g")
        {
            int newGesture = params.toInt();
            if (newGesture >= 0 && newGesture < NUM_GESTURES)
            {
                gesture = newGesture;
                Serial.println("TCP: Set gesture " + String(gesture));
                tcpClient.println("OK");
                status_changed = true;
            }
            else
            {
                tcpClient.println("ERROR: Invalid gesture");
            }
        }
        else if (cmdType == "p")
        {
            int colonIndex2 = params.indexOf(':');
            if (colonIndex2 > 0)
            {
                int flex = params.substring(0, colonIndex2).toInt();
                int ext = params.substring(colonIndex2 + 1).toInt();
                if (flex >= 0 && flex <= 100 && ext >= 0 && ext <= 100)
                {
                    pressure[0] = flex;
                    pressure[1] = ext;
                    Serial.println("TCP: Set pressure " + String(pressure[0]) + ":" + String(pressure[1]));
                    tcpClient.println("OK");
                    status_changed = true;
                }
                else
                {
                    tcpClient.println("ERROR: Invalid pressure values");
                }
            }
            else
            {
                tcpClient.println("ERROR: Invalid pressure format");
            }
        }
        else if (cmdType == "s")
        {
            int newSpeed = params.toInt();
            if (newSpeed >= 0 && newSpeed <= 4)
            {
                speed = newSpeed;
                Serial.println("TCP: Set speed " + String(speed));
                tcpClient.println("OK");
                status_changed = true;
            }
            else
            {
                tcpClient.println("ERROR: Invalid speed");
            }
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
    tcpClient.flush(); // Ensure response is sent immediately
}

// ==================== Actuator Update ====================
void updateActuators()
{
    // Convert gesture to finger states
    gestureToFingerStates();

    // Set finger states
    setFingerStates();

    // Set pressure and speed
    if (dac_available)
    {
        setPressureDAC();
        setSpeedDAC();
    }
}

// ==================== Gesture Conversion ====================
void gestureToFingerStates()
{
    static int lastGesture = -1;

    if (gesture != lastGesture)
    {
        String oldFingerStates = finger_states;
        lastGesture = gesture;

        if (gesture >= 0 && gesture < NUM_GESTURES)
        {
            finger_states = GESTURE_TO_FINGER_STATES_MAP[gesture];
        }
        else
        {
            finger_states = GESTURE_TO_FINGER_STATES_MAP[0]; // Default to Relax
        }

        status_changed = true;
        if (finger_states != oldFingerStates)
        {
            Serial.println("Gesture " + String(gesture) + " -> finger_states: " + oldFingerStates + " => " + finger_states);
        }
    }
}

// ==================== Finger States Setting ====================
void setFingerStates()
{
    if (finger_states.length() != 6)
        return;

    // Set 5 fingers
    for (int i = 0; i < 5; i++)
    {
        char state = finger_states.charAt(i);

        // Turn off all pins first
        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);

        // Set corresponding pin based on state
        switch (state)
        {
        case '1':
            digitalWrite(flexion_pins[i], HIGH);
            break; // Flexion
        case '2':
            digitalWrite(extension_pins[i], HIGH);
            break; // Extension
        case '3':
            digitalWrite(pinching_pins[i], HIGH);
            break; // Pinching
        default:
            break; // Relax state, all pins are LOW
        }
    }

    // Set abduction/adduction
    char abd_state = finger_states.charAt(5);
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);

    if (abd_state == '1')
    {
        digitalWrite(adduction_pin, HIGH); // Adduction
    }
    else if (abd_state == '2')
    {
        digitalWrite(abduction_pin, HIGH); // Abduction
    }
}

// ==================== Pressure DAC Setting ====================
void setPressureDAC()
{
    if (!dac_available)
        return;

    int flex_dac = (pressure[0] * 4095) / 100;
    int ext_dac = (pressure[1] * 4095) / 100;

    dac.setChannelValue(MCP4728_CHANNEL_A, ext_dac);  // Extension pressure
    dac.setChannelValue(MCP4728_CHANNEL_B, flex_dac); // Flexion pressure
}

// ==================== Speed DAC Setting ====================
void setSpeedDAC()
{
    if (!dac_available)
        return;

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

// ==================== Emergency Stop ====================
void emergencyStop()
{
    Serial.println("EMERGENCY STOP!");

    gesture = 0;
    pressure[0] = 0;
    pressure[1] = 0;
    speed = 0;
    finger_states = "000000";
    status_changed = true;

    // Immediately turn off all pins
    for (int i = 0; i < 5; i++)
    {
        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);
    }
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);

    // Turn off DAC outputs
    if (dac_available)
    {
        dac.setChannelValue(MCP4728_CHANNEL_A, 0);
        dac.setChannelValue(MCP4728_CHANNEL_B, 0);
        dac.setChannelValue(MCP4728_CHANNEL_C, 0);
        dac.setChannelValue(MCP4728_CHANNEL_D, 0);
    }
}
