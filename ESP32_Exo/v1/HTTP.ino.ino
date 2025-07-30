// External variable declarations
extern WebServer server;
extern int gesture;
extern int pressure[2];
extern int speed;
extern ControlMode control_mode;
extern int data_glove;
extern bool data_glove_initialized;
extern bool mcp4728_available;
extern const int pressure_max;

// External function declarations
void update_pressure();
void update_speed();
void init_wifi_direct();
bool safe_init_dac();
bool safe_init_data_glove();

// HTML web page content
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML>
<html>
<head>
  <title>Glove Control</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      text-align: center;
      background-color: #f4f4f4;
    }
    .card {
      background-color: white;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      margin: 15px auto;
      max-width: 600px;
      padding: 20px;
    }
    h1 {
      color: #0066cc;
    }
    h2 {
      color: #444;
      border-bottom: 1px solid #ddd;
      padding-bottom: 10px;
    }
    .button-group {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 10px;
      margin: 15px 0;
    }
    .control-group {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 15px 0;
    }
    input {
      width: 80px;
      padding: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
    }
    button {
      background-color: #0066cc;
      border: none;
      border-radius: 4px;
      color: white;
      cursor: pointer;
      font-size: 16px;
      padding: 10px 15px;
      min-width: 80px;
    }
    button:hover {
      background-color: #0055aa;
    }
    button.active {
      background-color: #22aa22;
    }
    button.mode {
      flex: 1;
      max-width: 120px;
    }
    .status {
      color: #666;
      font-style: italic;
      margin-top: 10px;
    }
    label {
      display: inline-block;
      width: 120px;
      text-align: right;
      margin-right: 10px;
    }
    #connectionInfo {
      background-color: #f8f9fa;
      border-radius: 5px;
      padding: 10px;
      margin-top: 20px;
      font-size: 14px;
      text-align: center;
      color: #666;
    }
    #wifiInfo {
      display: none;
      background-color: #e6f7ff;
      border: 1px solid #91d5ff;
      border-radius: 5px;
      padding: 15px;
      margin-top: 20px;
    }
    code {
      display: block;
      background-color: #f0f0f0;
      padding: 10px;
      border-radius: 4px;
      text-align: left;
      font-family: monospace;
      margin: 10px 0;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  <h1>ESP32 Glove Control System</h1>
  
  <div class="card">
    <h2>Control Mode</h2>
    <div class="button-group">
      <button class="mode" id="httpMode" onclick="setMode(0)">HTTP Mode</button>
      <button class="mode" id="serialMode" onclick="setMode(1)">Serial Mode</button>
      <button class="mode" id="dataGloveMode" onclick="setMode(2)">Data Glove</button>
      <button class="mode" id="wifiMode" onclick="setMode(3)">WiFi Control</button>
    </div>
    <p class="status" id="modeStatus">Current mode: HTTP Mode</p>
  </div>
  
  <div class="card">
    <h2>Gestures</h2>
    <div class="button-group">
      <button onclick="setGesture(0)">Relax</button>
      <button onclick="setGesture(1)">All Flex</button>
      <button onclick="setGesture(2)">All Extend</button>
      <button onclick="setGesture(3)">2-Finger Pinch</button>
      <button onclick="setGesture(4)">3-Finger Pinch</button>
      <button onclick="setGesture(5)">Thumb</button>
      <button onclick="setGesture(6)">Index</button>
      <button onclick="setGesture(7)">Middle</button>
      <button onclick="setGesture(8)">Yeah</button>
    </div>
    <p class="status" id="gestureStatus">Current gesture: Relax</p>
  </div>
  
  <div class="card">
    <h2>Pressure Control</h2>
    <div class="control-group">
      <label>Flexion:</label>
      <input type="number" id="flexionPressure" min="0" max="100" value="50">
      <button onclick="setPressure()">Set</button>
    </div>
    <div class="control-group">
      <label>Extension:</label>
      <input type="number" id="extensionPressure" min="0" max="100" value="50">
      <button onclick="setPressure()">Set</button>
    </div>
    <p class="status" id="pressureStatus">Current pressure: Flexion 50, Extension 50</p>
  </div>
  
  <div class="card">
    <h2>Speed Control</h2>
    <div class="control-group">
      <label>Speed Level:</label>
      <input type="number" id="speedValue" min="0" max="4" value="1">
      <button onclick="setSpeed()">Set</button>
    </div>
    <p class="status" id="speedStatus">Current speed: 1</p>
  </div>

  <div id="wifiInfo">
    <h3>WiFi Control Instructions</h3>
    <p>The device is now in WiFi control mode. Connect your computer to the ESP32_Glove WiFi network and use Python to control it:</p>
    <code>
import socket
import time

# ESP32 IP address and port
UDP_IP = "192.168.4.1"  # ESP32's IP address
UDP_PORT = 4210         # UDP port

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Example commands:
# Set gesture: sock.sendto(b"g:3", (UDP_IP, UDP_PORT))
# Set pressure: sock.sendto(b"p:40:30", (UDP_IP, UDP_PORT))
# Set speed: sock.sendto(b"s:4", (UDP_IP, UDP_PORT))
# Set finger states directly: sock.sendto(b"f:123400", (UDP_IP, UDP_PORT))
# Stop: sock.sendto(b"stop", (UDP_IP, UDP_PORT))
    </code>
  </div>

  <p id="connectionInfo">Connected to ESP32_Glove WiFi Network</p>

  <script>
    // Set control mode
    function setMode(mode) {
      document.getElementById('modeStatus').innerHTML = "Setting mode...";
      
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/setMode?mode=" + mode + "&t=" + new Date().getTime(), true);
      xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
          if (xhr.status == 200) {
            var modeNames = ["HTTP Mode", "Serial Mode", "Data Glove Mode", "WiFi Control Mode"];
            document.getElementById('modeStatus').innerHTML = "Current mode: " + modeNames[mode];
            
            // Update button styles
            document.getElementById('httpMode').className = "mode";
            document.getElementById('serialMode').className = "mode";
            document.getElementById('dataGloveMode').className = "mode";
            document.getElementById('wifiMode').className = "mode";
            
            if (mode == 0) document.getElementById('httpMode').className = "mode active";
            if (mode == 1) document.getElementById('serialMode').className = "mode active";
            if (mode == 2) document.getElementById('dataGloveMode').className = "mode active";
            if (mode == 3) document.getElementById('wifiMode').className = "mode active";
            
            // Show/hide WiFi instructions
            document.getElementById('wifiInfo').style.display = (mode == 3) ? 'block' : 'none';
          } else {
            document.getElementById('modeStatus').innerHTML = "Error setting mode";
          }
        }
      };
      xhr.send();
    }
    
    // Set gesture
    function setGesture(gesture) {
      document.getElementById('gestureStatus').innerHTML = "Setting gesture...";
      
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/setGesture?gesture=" + gesture + "&t=" + new Date().getTime(), true);
      xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
          if (xhr.status == 200) {
            var gestureNames = ["Relax", "All Flex", "All Extend", "2-Finger Pinch", 
                              "3-Finger Pinch", "Thumb", "Index", "Middle", "Yeah"];
            document.getElementById('gestureStatus').innerHTML = "Current gesture: " + gestureNames[gesture];
          } else {
            document.getElementById('gestureStatus').innerHTML = "Error setting gesture";
          }
        }
      };
      xhr.send();
    }
    
    // Set pressure
    function setPressure() {
      var flexion = document.getElementById('flexionPressure').value;
      var extension = document.getElementById('extensionPressure').value;
      
      document.getElementById('pressureStatus').innerHTML = "Setting pressure...";
      
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/setPressure?flexion=" + flexion + "&extension=" + extension + "&t=" + new Date().getTime(), true);
      xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
          if (xhr.status == 200) {
            document.getElementById('pressureStatus').innerHTML = 
              "Current pressure: Flexion " + flexion + ", Extension " + extension;
          } else {
            document.getElementById('pressureStatus').innerHTML = "Error setting pressure";
          }
        }
      };
      xhr.send();
    }
    
    // Set speed
    function setSpeed() {
      var speed = document.getElementById('speedValue').value;
      
      document.getElementById('speedStatus').innerHTML = "Setting speed...";
      
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/setSpeed?speed=" + speed + "&t=" + new Date().getTime(), true);
      xhr.onreadystatechange = function() {
        if (xhr.readyState == 4) {
          if (xhr.status == 200) {
            document.getElementById('speedStatus').innerHTML = "Current speed: " + speed;
          } else {
            document.getElementById('speedStatus').innerHTML = "Error setting speed";
          }
        }
      };
      xhr.send();
    }
    
   // Initialize the active mode
    window.onload = function() {
      // Set the default (HTTP) mode active
      document.getElementById('httpMode').className = "mode active";
    }
  </script>
</body>
</html>
)rawliteral";

void init_http_server() {
  Serial.println("\n[HTTP] Initializing HTTP server...");
  
  // Set WiFi to AP mode only
  WiFi.mode(WIFI_AP);
  
  // Configure AP for better performance
  WiFi.setSleep(false);  // Disable sleep mode to improve responsiveness
  
  // Create access point with custom SSID and password
  const char* ap_ssid = "ESP32_Glove";
  const char* ap_password = "12345678";
  
  // Start the access point
  bool result = WiFi.softAP(ap_ssid, ap_password);
  
  if (result) {
    Serial.println("[WIFI] Access Point created successfully");
    Serial.print("[WIFI] Network name: ");
    Serial.println(ap_ssid);
    Serial.print("[WIFI] Password: ");
    Serial.println(ap_password);
    Serial.print("[WIFI] IP address: ");
    Serial.println(WiFi.softAPIP());  // Usually 192.168.4.1
  } else {
    Serial.println("[WIFI] Failed to create Access Point!");
    return;  // Don't proceed if AP setup failed
  }
  
  // Define server routes
  server.on("/", HTTP_GET, handle_root);
  server.on("/setGesture", HTTP_GET, handle_set_gesture);
  server.on("/setPressure", HTTP_GET, handle_set_pressure);
  server.on("/setSpeed", HTTP_GET, handle_set_speed);
  server.on("/setMode", HTTP_GET, handle_set_mode);
  
  // Start server
  server.begin();
  Serial.println("[HTTP] Server started");
  Serial.println("[HTTP] To use this interface:");
  Serial.println("[HTTP] 1. Connect your device to the 'ESP32_Glove' WiFi network");
  Serial.println("[HTTP] 2. Password: 12345678");
  Serial.println("[HTTP] 3. Open 192.168.4.1 in your browser");
}

void handle_root() {
  // Add headers for better compatibility and faster response
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "-1");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/html", index_html);
}

void handle_set_gesture() {
  if (server.hasArg("gesture")) {
    int new_gesture = server.arg("gesture").toInt();
    
    if (new_gesture >= 0 && new_gesture <= 8) {
      gesture = new_gesture;
      
      Serial.print("[HTTP] Set gesture: ");
      Serial.println(gesture);
      
      // If gesture is set to 0 (relax) and we're not in data glove mode,
      // we'll want to update pressure and speed right away since they'll be overridden to 0
      if (gesture == 0 && control_mode != DATA_GLOVE_MODE) {
        Serial.println("[HTTP] Gesture set to RELAX (non-data-glove mode), automatically setting pressure and speed to 0");
        if (mcp4728_available) {
          update_pressure();
          update_speed();
        }
      }
      
      server.send(200, "text/plain", "OK");
    } else {
      server.send(400, "text/plain", "Invalid gesture value");
    }
  } else {
    server.send(400, "text/plain", "Missing gesture parameter");
  }
}

void handle_set_pressure() {
  if (server.hasArg("flexion") && server.hasArg("extension")) {
    int flexion = server.arg("flexion").toInt();
    int extension = server.arg("extension").toInt();
    
    if (flexion >= 0 && flexion <= pressure_max && extension >= 0 && extension <= pressure_max) {
      pressure[0] = flexion;
      pressure[1] = extension;
      
      Serial.print("[HTTP] Set pressure: Flexion=");
      Serial.print(pressure[0]);
      Serial.print(", Extension=");
      Serial.println(pressure[1]);
      
      // Initialize DAC if needed and update pressure
      if (mcp4728_available) {
        update_pressure();
      } else {
        Serial.println("[HTTP] Warning: DAC not available for pressure control");
      }
      
      server.send(200, "text/plain", "OK");
    } else {
      server.send(400, "text/plain", "Invalid pressure values");
    }
  } else {
    server.send(400, "text/plain", "Missing pressure parameters");
  }
}

void handle_set_speed() {
  if (server.hasArg("speed")) {
    int new_speed = server.arg("speed").toInt();
    
    if (new_speed >= 0 && new_speed <= 4) {
      speed = new_speed;
      
      Serial.print("[HTTP] Set speed: ");
      Serial.println(speed);
      
      // Initialize DAC if needed and update speed
      if (mcp4728_available) {
        update_speed();
      } else {
        Serial.println("[HTTP] Warning: DAC not available for speed control");
      }
      
      server.send(200, "text/plain", "OK");
    } else {
      server.send(400, "text/plain", "Invalid speed value");
    }
  } else {
    server.send(400, "text/plain", "Missing speed parameter");
  }
}

void handle_set_mode() {
  if (server.hasArg("mode")) {
    int mode = server.arg("mode").toInt();
    
    if (mode >= 0 && mode <= 3) {
      if (mode == 0) {
        control_mode = HTTP_MODE;
        data_glove = 0;
        Serial.println("[HTTP] Mode set to HTTP");
        
        // Initialize DAC for pressure and speed control in HTTP mode
        safe_init_dac();
      } else if (mode == 1) {
        control_mode = SERIAL_MODE;
        data_glove = 0;
        Serial.println("[HTTP] Mode set to Serial");
        
        // Initialize DAC for pressure and speed control in Serial mode
        safe_init_dac();
      } else if (mode == 2) {
        control_mode = DATA_GLOVE_MODE;
        data_glove = 1;
        
        // Initialize data glove when this mode is selected
        if (!data_glove_initialized) {
          Serial.println("[HTTP] Initializing data glove for Data Glove Mode");
          safe_init_data_glove();
        }
        
        // Initialize DAC for pressure and speed in Data Glove mode
        safe_init_dac();
        
        Serial.println("[HTTP] Mode set to Data Glove");
      } else if (mode == 3) {
        control_mode = WIFI_MODE;
        data_glove = 0;
        
        // Initialize WiFi direct control
        init_wifi_direct();
        
        // Initialize DAC for pressure and speed in WiFi mode
        safe_init_dac();
        
        Serial.println("[HTTP] Mode set to WiFi Control");
        Serial.println("[HTTP] UDP server ready on port 4210");
      }
      
      server.send(200, "text/plain", "OK");
    } else {
      server.send(400, "text/plain", "Invalid mode value");
    }
  } else {
    server.send(400, "text/plain", "Missing mode parameter");
  }
}