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
enum ControlMode
{
    WEB_MODE,
    TCP_MODE,
    BUTTON_MODE
};
ControlMode control_mode = WEB_MODE;

enum ControlModeLock
{
    AUTO_MODE,
    FORCE_WEB_MODE,
    FORCE_TCP_MODE,
    FORCE_BUTTON_MODE
};
ControlModeLock mode_lock = AUTO_MODE;

int gesture = 0;
int pressure[2] = {50, 50};
int speed = 1;
String finger_states = "000000";

const char *GESTURE_TO_FINGER_STATES_MAP[] = {
    "000000", "111110", "222222", "011110", "111110",
    "100000", "010000", "001110", "121110"};
const int NUM_GESTURES = sizeof(GESTURE_TO_FINGER_STATES_MAP) / sizeof(GESTURE_TO_FINGER_STATES_MAP[0]);

WebServer server(80);
WiFiServer tcpServer(tcp_port);
WiFiClient tcpClient;
Adafruit_MCP4728 dac;
bool dac_available = false;

bool tcp_connected = false;
unsigned long last_tcp_command = 0;
const unsigned long tcp_timeout = 20000;
char tcp_command_buffer[256];
int tcp_buffer_idx = 0;

bool status_changed = true;

// STA connection state variables - NEW: for manual connection
bool sta_connecting = false;
bool sta_connect_requested = false;
unsigned long sta_connect_start = 0;
const unsigned long sta_connect_timeout = 15000; // 15 seconds timeout

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
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
        * { box-sizing: border-box; touch-action: manipulation; }
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
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
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
        .status-connecting { background: #ffc107; }
        .realtime-display { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin: 15px 0; }
        .gesture-display { font-size: 20px; font-weight: bold; margin: 8px 0; }
        .btn-config { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 10px 0; }
        .pos-card { background: #f8f9fa; padding: 10px; border-radius: 6px; border: 2px solid #ddd; }
        .pos-card.active { border-color: #007bff; background: #e7f3ff; }
        .pos-label { font-weight: bold; color: #666; margin-bottom: 8px; font-size: 13px; }
        .pos-current { text-align: center; margin: 10px 0; font-size: 15px; }
        .pos-current span { font-weight: bold; color: #007bff; font-size: 18px; }
        
        /* Patient Big Button Styles */
        .patient-button-section {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 30px 20px;
            border-radius: 15px;
            margin: 20px 0;
        }
        .patient-button-section h3 { color: #e94560; margin: 0 0 20px 0; }
        .big-patient-button {
            width: 200px; height: 200px;
            border-radius: 50%;
            background: linear-gradient(145deg, #e94560, #c73b54);
            border: none;
            box-shadow: 
                0 15px 35px rgba(233,69,96,0.4),
                0 5px 15px rgba(0,0,0,0.3),
                inset 0 -8px 20px rgba(0,0,0,0.2),
                inset 0 8px 20px rgba(255,255,255,0.1);
            cursor: pointer;
            display: inline-flex;
            align-items: center; justify-content: center;
            flex-direction: column;
            transition: all 0.1s ease;
            -webkit-tap-highlight-color: transparent;
        }
        .big-patient-button:active {
            transform: scale(0.95);
            box-shadow: 
                0 5px 15px rgba(233,69,96,0.3),
                0 2px 8px rgba(0,0,0,0.2),
                inset 0 4px 15px rgba(0,0,0,0.3);
        }
        .big-patient-button:disabled {
            background: linear-gradient(145deg, #666, #555);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            cursor: not-allowed;
        }
        .big-patient-button .icon { font-size: 50px; color: white; text-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        .big-patient-button .text { font-size: 20px; color: white; font-weight: bold; margin-top: 8px; letter-spacing: 2px; }
        .patient-status { color: #94b4c1; margin-top: 15px; font-size: 14px; }
        .patient-status span { color: #00ff88; font-weight: bold; }
        .patient-feedback {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%) scale(0);
            background: rgba(0,255,136,0.95); color: #1a1a2e;
            padding: 30px 60px; border-radius: 15px;
            font-size: 28px; font-weight: bold;
            pointer-events: none; opacity: 0;
            transition: all 0.2s ease;
            z-index: 1000;
        }
        .patient-feedback.show {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ESP32 Glove Control</h1>
        
        <!-- Patient Big Button Section - Always visible for easy access -->
        <div class="patient-button-section">
            <h3>🎯 Patient Control Button</h3>
            <button class="big-patient-button" id="patientButton" ontouchstart="patientPress(event)" onmousedown="patientPress(event)">
                <span class="icon">👆</span>
                <span class="text">PRESS</span>
            </button>
            <div class="patient-status">
                Mode: <span id="patient-mode">--</span> | 
                Position: <span id="patient-position">0</span> |
                Gesture: <span id="patient-gesture">--</span>
            </div>
        </div>
        
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
                    <span id="sta-status">Disconnected</span>
                    <button id="sta-connect-btn" class="btn-success" onclick="connectSTA()" style="margin-left: 10px; padding: 4px 8px; font-size: 11px;">Connect</button>
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
    
    <div class="patient-feedback" id="patientFeedback">✓ SENT!</div>

    <script>
        const gestureNames = ["Relax", "HandClose", "HandOpen", "HookGrasp", "LateralGrasp", "ThumbFlex", "IndexFlex", "MRPFlex", "IndexPoint"];
        let lastPatientPress = 0;
        const patientDebounceMs = 200;
        
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
        
        function patientPress(e) {
            e.preventDefault();
            
            const now = Date.now();
            if (now - lastPatientPress < patientDebounceMs) return;
            lastPatientPress = now;
            
            playBeep();
            
            fetch('/web-button-press')
                .then(response => response.json())
                .then(data => {
                    showPatientFeedback(data.gesture || 'OK');
                    setTimeout(updateStatus, 100);
                })
                .catch(err => {
                    showPatientFeedback('SENT');
                });
        }
        
        function showPatientFeedback(text) {
            const fb = document.getElementById('patientFeedback');
            fb.textContent = '✓ ' + text;
            fb.classList.add('show');
            setTimeout(() => fb.classList.remove('show'), 400);
        }
        
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
                    
                    // Update patient button status
                    const patientBtn = document.getElementById('patientButton');
                    const patientMode = document.getElementById('patient-mode');
                    patientMode.textContent = data.mode;
                    
                    if (data.mode === 'BUTTON') {
                        patientBtn.disabled = false;
                        patientBtn.querySelector('.text').textContent = 'PRESS';
                    } else {
                        patientBtn.disabled = false; // Keep enabled, will auto-switch to BUTTON mode
                        patientBtn.querySelector('.text').textContent = 'PRESS';
                    }
                    
                    if (data.button_config) {
                        document.getElementById('patient-position').textContent = data.button_config.position;
                        const gestureIdx = data.button_config.gestures[data.button_config.position];
                        document.getElementById('patient-gesture').textContent = gestureNames[gestureIdx] || 'Unknown';
                    }
                    
                    const staDot = document.getElementById('sta-dot');
                    const staStatus = document.getElementById('sta-status');
                    const staBtn = document.getElementById('sta-connect-btn');
                    
                    if (data.sta_connecting) {
                        staDot.className = 'status-dot status-connecting';
                        staStatus.textContent = 'Connecting...';
                        staBtn.disabled = true;
                        staBtn.textContent = 'Connecting...';
                    } else if (data.sta_connected) {
                        staDot.className = 'status-dot status-online';
                        staStatus.textContent = data.sta_ip;
                        staBtn.disabled = true;
                        staBtn.textContent = 'Connected';
                        staBtn.className = 'btn-secondary';
                    } else {
                        staDot.className = 'status-dot status-offline';
                        staStatus.textContent = 'Disconnected';
                        staBtn.disabled = false;
                        staBtn.textContent = 'Connect';
                        staBtn.className = 'btn-success';
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
            return fetch(url).then(response => response.text());
        }
        
        function connectSTA() {
            sendCommand('sta-connect').then(() => setTimeout(updateStatus, 100));
        }
        
        function setGesture(id) { sendCommand('gesture', `value=${id}`); }
        function setPressure() { sendCommand('pressure', `flex=${document.getElementById('flex-pressure').value}&ext=${document.getElementById('ext-pressure').value}`); }
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
void handleSTAConnection();
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

// ==================== Main Program ====================
void setup()
{
    Serial.begin(115200);
    delay(500);

    Serial.println("\n=== ESP32 Glove Control System V4 ===");
    Serial.println("Initializing...");

    initHardware();
    initNetworks();
    initButtonBridge();
    initDAC();

    Serial.println("=== System Ready ===");
    Serial.println("Web Interface: 192.168.4.1");
    Serial.print("TCP Server (AP): ");
    Serial.print(WiFi.softAPIP());
    Serial.print(":");
    Serial.println(tcp_port);
    Serial.println("STA: Manual connection via web interface");
    Serial.println("====================");
}

void loop()
{
    // Emergency stop check (highest priority)
    if (digitalRead(emergency_pin) == LOW)
    {
        emergencyStop();
        delay(100);
        return;
    }

    // Handle all communication interfaces (non-blocking)
    server.handleClient();
    handleTCPCommands();
    handleSTAConnection(); // NEW: Non-blocking STA connection handler

    // Button bridge polling (fast response)
    pollButtonBridgeInterfaces();

    // TCP timeout management
    if (tcp_connected && (millis() - last_tcp_command > tcp_timeout))
    {
        Serial.println("TCP timeout");
        tcp_connected = false;
        if (mode_lock == AUTO_MODE)
            control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    if (tcp_connected && !tcpClient.connected())
    {
        Serial.println("TCP disconnected");
        tcp_connected = false;
        if (mode_lock == AUTO_MODE)
            control_mode = WEB_MODE;
        tcpClient.stop();
        status_changed = true;
    }

    // Update actuators
    updateActuators();

    // Minimal delay for stability (reduced from 5ms)
    delay(2);
}

// ==================== Hardware Initialization ====================
void initHardware()
{
    Serial.println("Init hardware...");

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

    Serial.println("Hardware OK");
}

// ==================== Button Bridge ====================
void initButtonBridge()
{
    Serial.println("Init button bridge...");

    if (button_bridge_serial_enabled)
    {
        button_serial.begin(115200, SERIAL_8N1, button_serial_rx_pin, button_serial_tx_pin);
        button_serial_buffer_idx = 0;
        Serial.printf("  Serial RX:%d TX:%d\n", button_serial_rx_pin, button_serial_tx_pin);
    }

    if (button_bridge_wifi_enabled)
    {
        button_udp_initialized = button_udp.begin(button_udp_port);
        if (button_udp_initialized)
        {
            Serial.printf("  UDP port %d\n", button_udp_port);
        }
    }

    Serial.println("Button bridge OK");
}

void pollButtonBridgeInterfaces()
{
    // Serial bridge (high priority)
    if (button_bridge_serial_enabled)
    {
        while (button_serial.available())
        {
            char c = button_serial.read();
            if (c == '\r' || c == '\n')
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
                button_serial_buffer[button_serial_buffer_idx++] = c;
            }
        }
    }

    // UDP bridge
    if (button_bridge_wifi_enabled && button_udp_initialized)
    {
        int packetSize = button_udp.parsePacket();
        if (packetSize > 0)
        {
            char udp_buffer[64];
            int len = button_udp.read(udp_buffer, sizeof(udp_buffer) - 1);
            if (len > 0)
            {
                udp_buffer[len] = '\0';
                processButtonCommand(String(udp_buffer), "UDP");
            }
        }
    }

    // Activity timeout tracking
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
    if (delimiterIndex < 0)
        delimiterIndex = normalized.indexOf('=');
    if (delimiterIndex < 0)
        delimiterIndex = normalized.indexOf(' ');

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
        return;

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
        Serial.printf("[BTN][%s] Ignored - not in BUTTON mode\n", source);
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

    Serial.printf("[BTN][%s] Pos=%d\n", source, button_cycle_position);
}

void applyButtonGesture(const char *source)
{
    if (control_mode == BUTTON_MODE)
    {
        int target_gesture = sanitizeGestureId(button_gestures[button_cycle_position]);
        if (gesture != target_gesture)
        {
            gesture = target_gesture;
            Serial.printf("[BTN][%s] Gesture=%d\n", source, gesture);
        }
    }
}

int sanitizeGestureId(int gestureId)
{
    return constrain(gestureId, 0, NUM_GESTURES - 1);
}

// ==================== Network Initialization (OPTIMIZED) ====================
void initNetworks()
{
    Serial.println("Init networks...");

    // Start AP mode only (fast startup)
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ap_ssid, ap_password);
    Serial.print("AP: ");
    Serial.println(WiFi.softAPIP());

    // Start TCP server immediately on AP
    tcpServer.begin();
    tcpServer.setNoDelay(true);
    Serial.println("TCP server ready");

    // Setup web server endpoints
    server.on("/", []()
              { server.send(200, "text/html", html_page); });

    // NEW: STA connection endpoint
    server.on("/sta-connect", []()
              {
        if (!sta_connecting && WiFi.status() != WL_CONNECTED)
        {
            sta_connect_requested = true;
            Serial.println("Web: STA connection requested");
            server.send(200, "text/plain", "Connecting...");
        }
        else if (WiFi.status() == WL_CONNECTED)
        {
            server.send(200, "text/plain", "Already connected");
        }
        else
        {
            server.send(200, "text/plain", "Connection in progress");
        } });

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
        json_doc["sta_connecting"] = sta_connecting;  // NEW
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
            gesture = sanitizeGestureId(server.arg("value").toInt());
            Serial.println("Web: gesture=" + String(gesture));
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/pressure", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("flex") && server.hasArg("ext")) {
            pressure[0] = constrain(server.arg("flex").toInt(), 0, 100);
            pressure[1] = constrain(server.arg("ext").toInt(), 0, 100);
            Serial.printf("Web: pressure=%d:%d\n", pressure[0], pressure[1]);
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/speed", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            speed = constrain(server.arg("value").toInt(), 0, 4);
            Serial.println("Web: speed=" + String(speed));
            status_changed = true;
        }
        server.send(200, "text/plain", "OK"); });

    server.on("/fingers", []()
              {
        if (control_mode == WEB_MODE && server.hasArg("value")) {
            String states = server.arg("value");
            if (states.length() == 6) {
                finger_states = states;
                Serial.println("Web: fingers=" + finger_states);
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
                Serial.println("Web: Mode=FORCE_WEB");
            }
            else if (mode == "TCP") {
                mode_lock = FORCE_TCP_MODE;
                control_mode = TCP_MODE;
                setButtonPosition(0, "WEB");
                Serial.println("Web: Mode=FORCE_TCP");
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
                Serial.println("Web: Mode=FORCE_BUTTON");
            }
            else if (mode == "AUTO") {
                mode_lock = AUTO_MODE;
                control_mode = tcp_connected ? TCP_MODE : WEB_MODE;
                if (control_mode != BUTTON_MODE) {
                    setButtonPosition(0, "WEB");
                }
                Serial.println("Web: Mode=AUTO");
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
                Serial.printf("Web: Cycle mode=%d\n", button_cycle_mode);
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
                Serial.printf("Web: Pos %d = gesture %d\n", pos, button_gestures[pos]);
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

    // Web GUI big button press endpoint - works like physical button
    server.on("/web-button-press", []()
              {
        // Auto-switch to BUTTON mode if not already
        if (control_mode != BUTTON_MODE)
        {
            mode_lock = FORCE_BUTTON_MODE;
            control_mode = BUTTON_MODE;
            if (tcp_connected)
            {
                tcpClient.stop();
                tcp_connected = false;
            }
            Serial.println("Web: Auto-switched to BUTTON mode");
        }
        
        // Advance the button cycle (same as physical button press)
        advanceButtonCycle("WEB-GUI");
        
        // Respond with current gesture info
        StaticJsonDocument<256> json_doc;
        char json_buffer[256];
        
        const char* gestureNames[] = {"Relax", "HandClose", "HandOpen", "HookGrasp", 
                                       "LateralGrasp", "ThumbFlex", "IndexFlex", "MRPFlex", "IndexPoint"};
        
        json_doc["status"] = "ok";
        json_doc["position"] = button_cycle_position;
        json_doc["gesture"] = gestureNames[gesture];
        json_doc["gesture_id"] = gesture;
        
        serializeJson(json_doc, json_buffer);
        server.send(200, "application/json", json_buffer); });

    server.begin();
    Serial.println("Web server ready");
}

// ==================== STA Connection Handler (NEW - NON-BLOCKING) ====================
void handleSTAConnection()
{
    // Check if connection was requested
    if (sta_connect_requested && !sta_connecting)
    {
        sta_connecting = true;
        sta_connect_start = millis();
        sta_connect_requested = false;

        Serial.println("Starting STA connection...");
        WiFi.mode(WIFI_AP_STA); // Switch to dual mode
        WiFi.begin(sta_ssid, sta_password);
    }

    // Handle ongoing connection attempt (non-blocking)
    if (sta_connecting)
    {
        wl_status_t status = WiFi.status();

        if (status == WL_CONNECTED)
        {
            sta_connecting = false;
            Serial.println("STA connected!");
            Serial.print("STA IP: ");
            Serial.println(WiFi.localIP());

            // TCP server is already running, it will now accept on both interfaces
        }
        else if (millis() - sta_connect_start > sta_connect_timeout)
        {
            sta_connecting = false;
            Serial.println("STA connection timeout");
            WiFi.mode(WIFI_AP); // Revert to AP-only mode
        }
        // Otherwise, connection is still in progress (non-blocking)
    }
}

// ==================== DAC Initialization ====================
void initDAC()
{
    Serial.println("Init DAC...");
    Wire.begin(sda_pin, scl_pin);

    if (dac.begin())
    {
        dac_available = true;
        dac.setChannelValue(MCP4728_CHANNEL_A, 0);
        dac.setChannelValue(MCP4728_CHANNEL_B, 0);
        dac.setChannelValue(MCP4728_CHANNEL_C, 0);
        dac.setChannelValue(MCP4728_CHANNEL_D, 0);
        Serial.println("DAC OK");
    }
    else
    {
        dac_available = false;
        Serial.println("DAC failed");
    }
}

// ==================== TCP Command Handler ====================
void handleTCPCommands()
{
    // Accept new connections
    if (!tcp_connected && tcpServer.hasClient())
    {
        if (mode_lock != FORCE_WEB_MODE)
        {
            if (tcpClient)
                tcpClient.stop();

            tcpClient = tcpServer.available();
            if (tcpClient)
            {
                tcp_connected = true;
                if (mode_lock == AUTO_MODE)
                {
                    control_mode = TCP_MODE;
                }
                tcp_buffer_idx = 0;
                Serial.print("TCP connected: ");
                Serial.println(tcpClient.remoteIP());

                tcpClient.println("ESP32 Glove Ready");
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
                rejectClient.println("ERROR: Forced WEB mode");
                rejectClient.stop();
            }
        }
    }

    // Process incoming data
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
}

void parseAndExecuteTCPCommand(String command)
{
    command.trim();
    if (command.length() == 0)
        return;

    last_tcp_command = millis();

    int colonIndex = command.indexOf(':');
    if (colonIndex > 0)
    {
        String cmdType = command.substring(0, colonIndex);
        String params = command.substring(colonIndex + 1);

        if (cmdType == "g")
        {
            gesture = sanitizeGestureId(params.toInt());
            Serial.println("TCP: gesture=" + String(gesture));
            tcpClient.println("OK");
            status_changed = true;
        }
        else if (cmdType == "p")
        {
            int colonIndex2 = params.indexOf(':');
            if (colonIndex2 > 0)
            {
                pressure[0] = constrain(params.substring(0, colonIndex2).toInt(), 0, 100);
                pressure[1] = constrain(params.substring(colonIndex2 + 1).toInt(), 0, 100);
                Serial.printf("TCP: pressure=%d:%d\n", pressure[0], pressure[1]);
                tcpClient.println("OK");
                status_changed = true;
            }
            else
            {
                tcpClient.println("ERROR: Invalid format");
            }
        }
        else if (cmdType == "s")
        {
            speed = constrain(params.toInt(), 0, 4);
            Serial.println("TCP: speed=" + String(speed));
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
                    Serial.println("TCP: fingers=" + finger_states);
                    tcpClient.println("OK");
                    status_changed = true;
                }
                else
                {
                    tcpClient.println("ERROR: Invalid states");
                }
            }
            else
            {
                tcpClient.println("ERROR: Must be 6 digits");
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
        tcpClient.println("ERROR: Invalid format");
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
        lastGesture = gesture;
        finger_states = GESTURE_TO_FINGER_STATES_MAP[gesture];
        status_changed = true;
    }
}

void setFingerStates()
{
    if (finger_states.length() != 6)
        return;

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
    if (!dac_available)
        return;

    int flex_dac = (pressure[0] * 4095) / 100;
    int ext_dac = (pressure[1] * 4095) / 100;

    dac.setChannelValue(MCP4728_CHANNEL_A, ext_dac);
    dac.setChannelValue(MCP4728_CHANNEL_B, flex_dac);
}

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
