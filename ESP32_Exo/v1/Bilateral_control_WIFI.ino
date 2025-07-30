#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Adafruit_MCP4728.h>
#include <Adafruit_MPR121.h>
#include <esp_task_wdt.h>
#include <esp_system.h>

// Wi-Fi settings
const char* ssid = "TP-Link_8541";
const char* password = "90872709";

// Create web server
WebServer server(80);

// Create MCP4728 DAC instance
Adafruit_MCP4728 dac;
bool dac_initialized = false;

// Uncomment for detailed WiFi debugging
// #define DEBUG_WIFI

////// Define Pins ////// 
///////////////////////////////////////////
// Define Pins for fingers
const int flexion_pins[5] = {13, 12, 14, 27, 27};
const int pinching_pins[5] = {15, 2, 4, 16, 32}; 
const int extension_pins[5] = {17, 5, 18, 19, 19};
const int abduction_pin = 25;
const int adduction_pin = 26;

// Pins for I2C data glove
const int sda_pin = 21;
const int scl_pin = 22;
const int emergency_switch_pin = 33;

////// Define Parameters ////// 
///////////////////////////////////////////
// Define control mode
enum ControlMode {DATA_GLOVE_MODE, SERIAL_MODE, HTTP_MODE, WIFI_MODE};

// Define finger states
int pressure[2] = {50, 50}; // pressure[0] for flexion, pressure[1] for extension
int glove_switch = 0;
const int pressure_max = 100;
const int pressure_serial = 50;
const int frequency = 10; // Hz
const int delay_time = 15; // Reduced from 20ms to 15ms for faster response
int cycle_number = 1;
int current_cycle = 0;
int gesture1_time = 2;
int gesture1_relax_time = 2;
int gesture2_time = 2;
int gesture2_relax_time = 2;
int gesture1 = 0;
int gesture2 = 0;
int gesture = 0;  // When gesture is 0, speed and pressure will be set to 0 automatically (only in HTTP and SERIAL modes)
int speed = 1;
int current_connection = 0;
int data_glove = 0;
bool data_glove_initialized = false;
bool i2c_initialized = false;
String finger_states = "000000"; //first five numbers for five fingers. 1st one for thumb. Last one for adduction
String massage = " ";
ControlMode control_mode = SERIAL_MODE;

// Device availability flags
bool mcp4728_available = false;
bool mpr121_available = false;

// Performance optimization variables
unsigned long lastUpdateTime = 0;
const unsigned long updateInterval = 15; // Update interval reduced from 20ms to 15ms

// Function declarations
void init_http_server();
void handle_root();
void handle_set_gesture();
void handle_set_pressure();
void handle_set_speed();
void handle_set_mode();
void update_cycle();
void serial_read_state();
void update_pressure();
void update_speed();
void update_hand_gesture();
void update_finger_states();
void init_data_glove();
void updata_data_glove();
bool init_dac();
void init_wifi_direct();
void handle_wifi_direct();
void process_wifi_command(char* command);
bool safe_scan_i2c();
bool safe_init_dac();
bool safe_init_data_glove();

void setup() {
    Serial.begin(115200);
    delay(1000); // Give serial time to stabilize
    
    Serial.println("\n=== ESP32 Glove Control System v2.0 ===");
    Serial.print("ESP32 Chip ID: ");
    Serial.println((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("Free Heap: ");
    Serial.println(ESP.getFreeHeap());
    Serial.print("Chip Revision: ");
    Serial.println(ESP.getChipRevision());
    
    // Detect reset reason
    esp_reset_reason_t reset_reason = esp_reset_reason();
    Serial.print("Reset reason: ");
    switch(reset_reason) {
        case ESP_RST_POWERON: Serial.println("Power-on reset"); break;
        case ESP_RST_EXT: Serial.println("External reset"); break;
        case ESP_RST_SW: Serial.println("Software reset"); break;
        case ESP_RST_PANIC: Serial.println("Exception/panic reset"); break;
        case ESP_RST_INT_WDT: Serial.println("Interrupt watchdog reset"); break;
        case ESP_RST_TASK_WDT: Serial.println("Task watchdog reset"); break;
        case ESP_RST_WDT: Serial.println("Other watchdog reset"); break;
        case ESP_RST_DEEPSLEEP: Serial.println("Deep sleep reset"); break;
        case ESP_RST_BROWNOUT: Serial.println("Brownout reset"); break;
        case ESP_RST_SDIO: Serial.println("SDIO reset"); break;
        default: Serial.println("Unknown reset"); break;
    }
    
    Serial.println("Initializing pins...");
    // Set pins as output without initializing I2C
    for (int i = 0; i < 5; i++) {
        pinMode(flexion_pins[i], OUTPUT);
        pinMode(extension_pins[i], OUTPUT);
        pinMode(pinching_pins[i], OUTPUT);
        digitalWrite(flexion_pins[i], LOW);
        digitalWrite(extension_pins[i], LOW);
        digitalWrite(pinching_pins[i], LOW);
    }
    pinMode(abduction_pin, OUTPUT);
    pinMode(adduction_pin, OUTPUT);
    digitalWrite(abduction_pin, LOW);
    digitalWrite(adduction_pin, LOW);
    pinMode(emergency_switch_pin, INPUT_PULLUP);
    
    Serial.println("Pins initialized successfully");
    
    // Initialize HTTP server
    Serial.println("Starting HTTP server...");
    init_http_server();
    
    // Initialize WiFi direct control - initialize in setup
    Serial.println("Starting WiFi UDP control...");
    init_wifi_direct();
    
    Serial.println("=== Setup Complete Successfully ===");
    Serial.println("Current control mode: SERIAL_MODE");
    Serial.println("Available commands:");
    Serial.println("- Web interface: 192.168.4.1");
    Serial.println("- UDP commands: 192.168.4.1:4210");
    Serial.println("- Serial commands: m 3 (set WiFi mode)");
    Serial.print("Free Heap after setup: ");
    Serial.println(ESP.getFreeHeap());
    Serial.println("==========================================");
}

// Safe I2C device scanning
bool safe_scan_i2c() {
    if (!i2c_initialized) {
        Serial.println("Initializing I2C bus...");
        Wire.begin(sda_pin, scl_pin);
        Wire.setClock(100000); // Lower I2C clock to 100kHz for stability
        i2c_initialized = true;
        delay(100);
    }
    
    Serial.println("Scanning I2C bus...");
    int deviceCount = 0;
    
    for (byte address = 1; address < 127; address++) {
        Wire.beginTransmission(address);
        byte error = Wire.endTransmission();
        
        if (error == 0) {
            deviceCount++;
            Serial.print("I2C device found at address 0x");
            if (address < 16) Serial.print("0");
            Serial.println(address, HEX);
            
            // Check if it's a known device
            if (address == 0x60 || address == 0x61 || address == 0x62 || address == 0x63) {
                Serial.println("  -> Possible MCP4728 DAC");
            } else if (address == 0x5A || address == 0x5B || address == 0x5C || address == 0x5D) {
                Serial.println("  -> Possible MPR121 Touch Sensor");
            }
        }
    }
    
    Serial.print("Total I2C devices found: ");
    Serial.println(deviceCount);
    
    return deviceCount > 0;
}

// Safe DAC initialization
bool safe_init_dac() {
    // Skip if already initialized and available
    if (dac_initialized && mcp4728_available) {
        return true;
    }
    
    // Initialize I2C if needed
    if (!i2c_initialized) {
        Wire.begin(sda_pin, scl_pin);
        Wire.setClock(100000);
        i2c_initialized = true;
        delay(100);
    }
    
    // Try to initialize DAC
    Serial.println("Attempting to initialize MCP4728 DAC...");
    
    if (dac.begin()) {
        mcp4728_available = true;
        dac_initialized = true;
        
        // Set all channels to 0 initially
        dac.setChannelValue(MCP4728_CHANNEL_A, 0);
        dac.setChannelValue(MCP4728_CHANNEL_B, 0);
        dac.setChannelValue(MCP4728_CHANNEL_C, 0);
        dac.setChannelValue(MCP4728_CHANNEL_D, 0);
        
        Serial.println("✓ MCP4728 DAC initialized successfully");
        return true;
    } else {
        mcp4728_available = false;
        //Serial.println("✗ Failed to initialize MCP4728 DAC");
        return false;
    }
}

// Safe data glove initialization - forward declaration
bool safe_init_data_glove();

// Function to initialize I2C and DAC only when needed
bool init_dac() {
    // Use safe DAC initialization for backward compatibility
    return safe_init_dac();
}

void loop() {
    static unsigned long lastMemoryCheck = 0;
    unsigned long currentTime = millis();
    
    // Memory check - every 10 seconds to reduce frequency
    if (currentTime - lastMemoryCheck > 10000) {
        uint32_t freeHeap = ESP.getFreeHeap();
        if (freeHeap < 10000) {
            Serial.print("⚠️  Low memory: ");
            Serial.print(freeHeap);
            Serial.println(" bytes");
        }
        lastMemoryCheck = currentTime;
    }
    
    // Check emergency stop
    if (digitalRead(emergency_switch_pin) == LOW) {  
        Serial.println("🚨 Emergency stop");
        gesture = 0;
        if (init_dac()) {
            update_pressure();
            update_speed();
        }
        return; // Return immediately on emergency stop
    }
    
    // Handle HTTP requests with simple error protection
    server.handleClient();
    
    // Handle WiFi direct commands  
    handle_wifi_direct();
    
    // Handle serial commands if available
    if (Serial.available() > 0) {
        serial_read_state();
    }

    // Control logic - simplified processing
    // Initialize DAC if pressure or speed needs to be updated
    // But only update if not in DATA_GLOVE_MODE to avoid I2C conflicts
    if (!data_glove && control_mode != DATA_GLOVE_MODE) {
        // Update pressure and speed only if DAC is initialized
        if (init_dac()) {
            update_pressure();
            update_speed();
        }
    } else if (data_glove == 1 && control_mode == DATA_GLOVE_MODE) {
        // In data glove mode, we still need to update pressure and speed
        // but without the automatic zero when gesture=0
        if (init_dac()) {
            update_pressure();
            update_speed();
        }
    }
    
    // Control logic based on mode
    if (data_glove == 1) {
        // Initialize data glove if not done already
        if (!data_glove_initialized) {
            init_data_glove();
        }
        
        if (data_glove_initialized) {
            updata_data_glove();
        } else {
            // If initialization failed, switch to default gesture mode
            update_hand_gesture();
        }
    } else if (control_mode == WIFI_MODE) {
        // In WiFi mode, finger_states are updated directly by UDP commands
        // Just ensure they're applied to the output pins
        update_finger_states();
    } else {
        update_hand_gesture();
    }
    
    // Only delay if enough time hasn't passed since last update
    // This provides more responsive control while maintaining timing
    unsigned long elapsedTime = millis() - currentTime;
    if (elapsedTime < delay_time) {
        delay(delay_time - elapsedTime);
    }
    
    // Yield CPU time to prevent watchdog reset
    yield();
}