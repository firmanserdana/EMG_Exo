#include <WiFi.h>
#include <WiFiUdp.h>

// External function declarations
void update_hand_gesture();
void update_pressure();
void update_speed();
void update_finger_states();
bool init_dac();

// External variable declarations
extern int gesture;
extern int pressure[2];
extern int speed;
extern String finger_states;
extern ControlMode control_mode;
extern int data_glove;
extern int glove_switch;
extern bool mcp4728_available;

// UDP server settings for WiFi control
WiFiUDP udp;
unsigned int udpPort = 4210;  // UDP port for receiving commands
char packetBuffer[255];       // Buffer for incoming UDP packets

// Flag to indicate if WiFi direct control is active
bool wifi_direct_enabled = false;

// Initialize UDP server for WiFi control
void init_wifi_direct() {
    // We'll use the same AP created in HTTP.ino
    // Just start UDP listener
    Serial.println("[WIFI] Initializing UDP server...");
    
    if (udp.begin(udpPort)) {
        wifi_direct_enabled = true;
        Serial.print("[WIFI] ✓ UDP server started successfully on port ");
        Serial.println(udpPort);
        Serial.print("[WIFI] Local IP: ");
        Serial.println(WiFi.softAPIP());
        Serial.println("[WIFI] Ready to receive commands from external software");
    } else {
        wifi_direct_enabled = false;
        Serial.println("[WIFI] ✗ Failed to start UDP server");
    }
}

// Process UDP commands from external software
void handle_wifi_direct() {
    if (!wifi_direct_enabled) {
        return; // Remove frequent debug output to reduce serial load
    }
    
    // Check if there's data available
    int packetSize = udp.parsePacket();
    if (packetSize) {
        // Check if packet size is reasonable
        if (packetSize > 254) {
            Serial.println("[WIFI] ⚠️  Packet too large, ignoring");
            return;
        }
        
        Serial.println("[WIFI] ✓ UDP packet detected!");
        Serial.print("[WIFI] Packet size: ");
        Serial.println(packetSize);
        
        // Read the packet into the buffer with bounds checking
        int len = udp.read(packetBuffer, min(packetSize, 254));
        if (len > 0 && len < 255) {
            packetBuffer[len] = 0; // Null-terminate the string
            
            Serial.print("[WIFI] Received from ");
            Serial.print(udp.remoteIP());
            Serial.print(": ");
            Serial.println(packetBuffer);
            
            // Process the command with error handling
            process_wifi_command(packetBuffer);
            
            // Send acknowledgment back
            udp.beginPacket(udp.remoteIP(), udp.remotePort());
            udp.print("ACK");
            udp.endPacket();
            
            Serial.println("[WIFI] ACK sent");
        } else {
            Serial.println("[WIFI] ⚠️  Invalid packet length");
        }
    }
}

// Process commands received via WiFi
void process_wifi_command(char* command) {
    if (!command || strlen(command) == 0) {
        Serial.println("[WIFI] Empty command received");
        return;
    }
    
    Serial.print("[WIFI] Processing: ");
    Serial.println(command);
    
    // Create a copy of the command to avoid strtok modifying original data
    char cmdCopy[256];
    strncpy(cmdCopy, command, 255);
    cmdCopy[255] = 0; // Ensure string termination
    
    // Parse command type
    char* cmd_type = strtok(cmdCopy, ":");
    if (!cmd_type) {
        Serial.println("[WIFI] Invalid command format");
        return;
    }
    
    if (strcmp(cmd_type, "g") == 0) {
        // Gesture command
        char* value = strtok(NULL, ":");
        if (value != NULL) {
            int new_gesture = atoi(value);
            if (new_gesture >= 0 && new_gesture <= 8) {
                gesture = new_gesture;
                Serial.print("[WIFI] ✓ Set gesture: ");
                Serial.println(gesture);
                
                // Update hand gesture immediately
                update_hand_gesture();
            } else {
                Serial.println("[WIFI] ⚠️  Invalid gesture value");
            }
        }
    } 
    else if (strcmp(cmd_type, "p") == 0) {
        // Pressure command
        char* flex_value = strtok(NULL, ":");
        char* ext_value = strtok(NULL, ":");
        
        if (flex_value != NULL && ext_value != NULL) {
            int flex = atoi(flex_value);
            int ext = atoi(ext_value);
            
            if (flex >= 0 && flex <= 100 && ext >= 0 && ext <= 100) {
                pressure[0] = flex;
                pressure[1] = ext;
                
                Serial.print("[WIFI] ✓ Set pressure: ");
                Serial.print(pressure[0]);
                Serial.print(":");
                Serial.println(pressure[1]);
                
                // Update pressure immediately with error handling
                if (init_dac()) {
                    update_pressure();
                    Serial.println("[WIFI] Pressure updated");
                } else {
                    Serial.println("[WIFI] ⚠️  DAC init failed");
                }
            } else {
                Serial.println("[WIFI] ⚠️  Invalid pressure values");
            }
        }
    } 
    else if (strcmp(cmd_type, "s") == 0) {
        // Speed command
        char* value = strtok(NULL, ":");
        if (value != NULL) {
            int new_speed = atoi(value);
            if (new_speed >= 0 && new_speed <= 4) {
                speed = new_speed;
                Serial.print("[WIFI] ✓ Set speed: ");
                Serial.println(speed);
                
                // Update speed immediately with error handling
                if (init_dac()) {
                    update_speed();
                    Serial.println("[WIFI] Speed updated");
                } else {
                    Serial.println("[WIFI] ⚠️  DAC init failed");
                }
            } else {
                Serial.println("[WIFI] ⚠️  Invalid speed value");
            }
        }
    } 
    else if (strcmp(cmd_type, "f") == 0) {
        // Direct finger states command
        char* value = strtok(NULL, ":");
        if (value != NULL && strlen(value) == 6) {
            // Validate string contains only valid characters
            bool valid = true;
            for (int i = 0; i < 6; i++) {
                if (value[i] < '0' || value[i] > '3') {
                    valid = false;
                    break;
                }
            }
            
            if (valid) {
                finger_states = String(value);
                Serial.print("[WIFI] ✓ Set finger_states: ");
                Serial.println(finger_states);
                
                update_finger_states();
                Serial.println("[WIFI] Finger states updated");
            } else {
                Serial.println("[WIFI] ⚠️  Invalid finger state characters");
            }
        } else {
            Serial.println("[WIFI] ⚠️  Invalid finger states format");
        }
    }
    else if (strcmp(cmd_type, "m") == 0) {
        // Mode command
        char* value = strtok(NULL, ":");
        if (value != NULL) {
            int mode = atoi(value);
            switch (mode) {
                case 0:
                    control_mode = HTTP_MODE;
                    data_glove = 0;
                    Serial.println("[WIFI] ✓ Mode set to HTTP");
                    break;
                case 1:
                    control_mode = SERIAL_MODE;
                    data_glove = 0;
                    Serial.println("[WIFI] ✓ Mode set to Serial");
                    break;
                case 2:
                    control_mode = DATA_GLOVE_MODE;
                    data_glove = 1;
                    Serial.println("[WIFI] ✓ Mode set to Data Glove");
                    break;
                case 3:
                    control_mode = WIFI_MODE;
                    data_glove = 0;
                    Serial.println("[WIFI] ✓ Mode set to WiFi Control");
                    break;
                default:
                    Serial.println("[WIFI] ⚠️  Invalid mode");
                    break;
            }
        }
    }
    else if (strcmp(cmd_type, "stop") == 0) {
        // Stop command
        glove_switch = 0;
        gesture = 0;
        Serial.println("[WIFI] ✓ Emergency stop");
        
        // Immediately update to stop state
        if (mcp4728_available) {
            update_pressure();
            update_speed();
        }
        update_finger_states();
    }
    else if (strcmp(cmd_type, "cycle") == 0) {
        // Cycle command - start a gesture cycle
        Serial.println("[WIFI] ✓ Starting gesture cycle");
        // Implement cycle logic if needed
    }
    else {
        Serial.print("[WIFI] ⚠️  Unknown command: ");
        Serial.println(cmd_type);
    }
}

/* Python code example for controlling the glove via WiFi
# This would be provided to the user separately

import socket
import time

# ESP32 IP address and port
UDP_IP = "192.168.4.1"  # ESP32's IP address in AP mode
UDP_PORT = 4210         # UDP port

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Switch to WiFi control mode
sock.sendto(b"m:3", (UDP_IP, UDP_PORT))
time.sleep(0.1)

# Set gesture to 3 (2-finger pinch)
sock.sendto(b"g:3", (UDP_IP, UDP_PORT))
time.sleep(0.1)

# Set pressure (flexion: 40, extension: 30)
sock.sendto(b"p:40:30", (UDP_IP, UDP_PORT))
time.sleep(0.1)

# Set speed to 4
sock.sendto(b"s:4", (UDP_IP, UDP_PORT))
time.sleep(0.1)

# Set finger states directly (custom finger configuration)
sock.sendto(b"f:123400", (UDP_IP, UDP_PORT))
time.sleep(0.1)

# Start a gesture cycle
sock.sendto(b"cycle", (UDP_IP, UDP_PORT))
time.sleep(5)

# Stop all actions
sock.sendto(b"stop", (UDP_IP, UDP_PORT))

# Example of real-time control loop
try:
    while True:
        # Send updated finger states every 50ms
        # This simulates real-time control similar to data glove
        sock.sendto(b"f:123400", (UDP_IP, UDP_PORT))
        time.sleep(0.05)  # 50ms update rate
except KeyboardInterrupt:
    # Send stop command when interrupted
    sock.sendto(b"stop", (UDP_IP, UDP_PORT))
*/