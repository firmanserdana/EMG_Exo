#include <WiFi.h>
#include <WebServer.h>
#include <WiFiClient.h>
#include <Wire.h>
#include <Adafruit_MCP4728.h>

// ==================== Configuration ====================
// WiFi AP Configuration (for web control)
const char *ap_ssid = "ESP32_Glove";
const char *ap_password = "12345678";

// WiFi STA Configuration (connect to computer WiFi)
const char *sta_ssid = "iFire (2)";      //
const char *sta_password = "7j@nuari07"; //

// TCP Configuration
const int tcp_port = 4210;

// ==================== Hardware Configuration ====================
// Finger control pins
const int flexion_pins[5] = {13, 12, 14, 27, 26};  // Flexion control pins
const int extension_pins[5] = {17, 5, 18, 19, 25}; // Extension control pins
const int pinching_pins[5] = {15, 2, 4, 16, 32};   // Pinching control pins
const int abduction_pin = 21;                      // Abduction pin
const int adduction_pin = 22;                      // Adduction pin
const int emergency_pin = 33;                      // Emergency stop pin

// I2C Configuration
const int sda_pin = 21;
const int scl_pin = 22;

// ==================== Global Variables ====================
// Control modes
enum ControlMode
{
    WEB_MODE,
    TCP_MODE
};
ControlMode control_mode = WEB_MODE;

// Gesture and states
int gesture = 0;                 // Gesture (0-8)
int pressure[2] = {50, 50};      // Pressure [flexion, extension] (0-100)
int speed = 1;                   // Speed (0-4)
String finger_states = "000000"; // Finger states string

// Hardware objects
WebServer server(80);
WiFiServer tcpServer(tcp_port);
WiFiClient tcpClient;
Adafruit_MCP4728 dac;
bool dac_available = false;

// Network status
bool tcp_connected = false;
unsigned long last_tcp_command = 0;
const unsigned long tcp_timeout = 5000; // 5 second timeout

// Status update flags
bool status_changed = true;

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
            <h3>Gesture Control</h3>
            <div class="button-group">
                <button class="btn-primary" onclick="setGesture(0)">Relax</button>
                <button class="btn-primary" onclick="setGesture(1)">All Flex</button>
                <button class="btn-primary" onclick="setGesture(2)">All Extend</button>
                <button class="btn-primary" onclick="setGesture(3)">2-Finger Pinch</button>
                <button class="btn-primary" onclick="setGesture(4)">3-Finger Pinch</button>
                <button class="btn-primary" onclick="setGesture(5)">Thumb</button>
                <button class="btn-primary" onclick="setGesture(6)">Index</button>
                <button class="btn-primary" onclick="setGesture(7)">Middle</button>
                <button class="btn-primary" onclick="setGesture(8)">Peace</button>
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
                <div>Connect from computer using: <strong>ESP32_IP:4210</strong></div>
                <div>Commands: g:X, p:X:Y, s:X, f:XXXXXX, stop</div>
            </div>
        </div>
    </div>

    <script>
        const gestureNames = ["Relax", "All Flex", "All Extend", "2-Finger Pinch", "3-Finger Pinch", "Thumb", "Index", "Middle", "Peace"];
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // Update mode indicator
                    const modeElement = document.getElementById('mode-status');
                    if (data.mode === 'TCP') {
                        modeElement.className = 'mode-indicator mode-tcp';
                        modeElement.textContent = 'TCP Control Mode (Computer Connected)';
                    } else {
                        modeElement.className = 'mode-indicator mode-web';
                        modeElement.textContent = 'Web Control Mode';
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
                    
                    // Update real-time status
                    document.getElementById('current-gesture').textContent = gestureNames[data.gesture] || 'Unknown';
                    document.getElementById('current-flex').textContent = data.pressure[0];
                    document.getElementById('current-ext').textContent = data.pressure[1];
                    document.getElementById('current-speed').textContent = data.speed;
                    document.getElementById('current-fingers').textContent = data.finger_states;
                    
                    // Update input fields with current values
                    document.getElementById('flex-pressure').value = data.pressure[0];
                    document.getElementById('ext-pressure').value = data.pressure[1];
                    document.getElementById('speed-level').value = data.speed;
                    document.getElementById('finger-states').value = data.finger_states;
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
void handleWebRequests();
void handleTCPCommands();
void updateActuators();
void gestureToFingerStates();
void setFingerStates();
void setPressureDAC();
void setSpeedDAC();
void emergencyStop();

// ==================== Main Program ====================
void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== ESP32 Glove Control System ===");
    Serial.println("Initializing...");

    initHardware();
    initNetworks();
    initDAC();

    Serial.println("=== System Ready ===");
    Serial.println("Web Interface: 192.168.4.1");
    Serial.println("TCP Server: Port 4210");
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

    // Check TCP connection timeout
    if (tcp_connected && (millis() - last_tcp_command > tcp_timeout))
    {
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        Serial.println("TCP connection timeout, switching to Web mode");
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
    }
    else
    {
        Serial.println("\nSTA connection failed, AP only mode");
    }

    // Start TCP server
    tcpServer.begin();
    Serial.print("TCP server started on port ");
    Serial.println(tcp_port);

    // Setup web server routes
    server.on("/", []()
              { server.send(200, "text/html", html_page); });

    server.on("/status", []()
              {
        String json = "{";
        json += "\"mode\":\"" + String(control_mode == TCP_MODE ? "TCP" : "WEB") + "\",";
        json += "\"sta_connected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
        json += "\"sta_ip\":\"" + WiFi.localIP().toString() + "\",";
        json += "\"tcp_connected\":" + String(tcp_connected ? "true" : "false") + ",";
        json += "\"tcp_client_ip\":\"" + (tcp_connected ? tcpClient.remoteIP().toString() : "none") + "\",";
        json += "\"gesture\":" + String(gesture) + ",";
        json += "\"pressure\":[" + String(pressure[0]) + "," + String(pressure[1]) + "],";
        json += "\"speed\":" + String(speed) + ",";
        json += "\"finger_states\":\"" + finger_states + "\"";
        json += "}";
        server.send(200, "application/json", json); });

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

    server.on("/stop", []()
              {
        emergencyStop();
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
        Serial.println("DAC initialization failed - using digital control only");
    }
}

// ==================== TCP Command Handler ====================
void handleTCPCommands()
{
    // Check for new TCP client connections
    if (!tcp_connected)
    {
        tcpClient = tcpServer.available();
        if (tcpClient)
        {
            tcp_connected = true;
            control_mode = TCP_MODE;
            Serial.print("TCP client connected from: ");
            Serial.println(tcpClient.remoteIP());
            status_changed = true;
        }
    }

    // Handle existing TCP client
    if (tcp_connected && tcpClient.connected())
    {
        if (tcpClient.available())
        {
            String command = tcpClient.readStringUntil('\n');
            command.trim();

            if (command.length() > 0)
            {
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
                        if (newGesture >= 0 && newGesture <= 8)
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
            }
        }
    }
    else if (tcp_connected)
    {
        // Client disconnected
        tcp_connected = false;
        control_mode = WEB_MODE;
        tcpClient.stop();
        Serial.println("TCP client disconnected, switching to Web mode");
        status_changed = true;
    }
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
    // Only update finger_states from gesture if not directly controlled
    static int lastGesture = -1;
    static unsigned long lastDirectControl = 0;

    // Check if finger_states was recently set directly (via TCP 'f' command or web)
    if (status_changed)
    {
        lastDirectControl = millis();
    }

    // Only convert gesture to finger_states if no direct control in last 100ms
    if (gesture != lastGesture && (millis() - lastDirectControl > 100))
    {
        lastGesture = gesture;

        switch (gesture)
        {
        case 0:
            finger_states = "000000";
            break; // Relax
        case 1:
            finger_states = "111110";
            break; // All flex
        case 2:
            finger_states = "222220";
            break; // All extend
        case 3:
            finger_states = "011110";
            break; // IMRP Flexion
        case 4:
            finger_states = "333000";
            break; // 3-finger pinch
        case 5:
            finger_states = "100000";
            break; // Thumb
        case 6:
            finger_states = "010000";
            break; // Index
        case 7:
            finger_states = "001110";
            break; // Middle, Ring, Pinky
        case 8:
            finger_states = "121110";
            break; // Index Pointing
        default:
            finger_states = "000000";
            break;
        }
        status_changed = true;
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