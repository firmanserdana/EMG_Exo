// Define MPR121
Adafruit_MPR121 capture = Adafruit_MPR121();

// Set threshold for finger sensor
const int flexion_threshold[5] = {170, 180, 170, 160, 170};
const int extension_threshold[5] = {130, 120, 125, 105, 145};
const int pinching_threshold[5] = {135, 135, 128, 140, 150};

// External variable declarations - import from main file
extern bool mpr121_available;
extern bool data_glove_initialized;
extern bool i2c_initialized;
extern String finger_states;
extern const int sda_pin;
extern const int scl_pin;

// Function to update finger states - declare it here
void update_finger_states();

// Safe data glove initialization implementation
bool safe_init_data_glove_impl() {
    // Initialize I2C if needed
    if (!i2c_initialized) {
        Wire.begin(sda_pin, scl_pin);
        Wire.setClock(100000); // 100kHz for stability
        i2c_initialized = true;
        delay(100);
    }
    
    Serial.println("Attempting to initialize MPR121 touch sensor...");
    
    // Try to find MPR121 at common addresses
    uint8_t addresses[] = {0x5A, 0x5B, 0x5C, 0x5D};
    
    for (uint8_t i = 0; i < 4; i++) {
        if (capture.begin(addresses[i])) {
            mpr121_available = true;
            data_glove_initialized = true;
            
            Serial.print("✓ MPR121 found at address 0x");
            Serial.println(addresses[i], HEX);
            
            // Configure touch thresholds
            capture.setThresholds(12, 6);
            
            Serial.println("✓ Data glove initialized successfully");
            return true;
        }
    }
    
    mpr121_available = false;
    data_glove_initialized = false;
    Serial.println("✗ Failed to initialize MPR121 - data glove not found");
    return false;
}

// Forward declaration for main file compatibility
bool safe_init_data_glove() {
    return safe_init_data_glove_impl();
}

void init_data_glove() {
    // Use safe data glove initialization
    safe_init_data_glove_impl();
}

void updata_data_glove() {
    // Verify data glove is available and initialized
    if (!mpr121_available || !data_glove_initialized) {
        static unsigned long lastWarning = 0;
        if (millis() - lastWarning > 10000) { // Warn every 10 seconds
            Serial.println("Warning: Data glove not available");
            lastWarning = millis();
        }
        return;
    }
    
    // Check if MPR121 is still responding
    uint16_t touched = capture.touched();
    
    String finger_state_glove = "";
    for (int i = 0; i < 5; i++) {
        int sensorValue = 0;
        
        // Protected sensor reading with error checking
        sensorValue = capture.filteredData(i);
        
        // Validate sensor value
        if (sensorValue < 0 || sensorValue > 1023) {
            Serial.print("Warning: Invalid sensor value for finger ");
            Serial.println(i);
            finger_state_glove += "0"; // Default to relaxed
            continue;
        }
        
        // Debug output - uncomment if needed
        // Serial.print("Sensor ");
        // Serial.print(i);
        // Serial.print(" value: ");
        // Serial.println(sensorValue);
        
        String state = "0"; // Default to relaxed state
        
        // Determine finger state based on thresholds
        if (sensorValue > flexion_threshold[i]) {
            state = "1"; // Flexion
        } else if (sensorValue < extension_threshold[i]) {
            state = "2"; // Extension
        } else if ((sensorValue < flexion_threshold[i]) && (sensorValue > pinching_threshold[i])) {
            state = "3"; // Pinching
        }

        // Add finger state to string
        finger_state_glove += state;
    }
    
    // Add abduction/adduction state (default to 0)
    finger_state_glove += "0";
    
    // Update global finger states
    finger_states = finger_state_glove;
    update_finger_states();
}