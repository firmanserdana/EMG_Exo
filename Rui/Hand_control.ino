// External variable declarations
extern bool mcp4728_available;
extern Adafruit_MCP4728 dac;
extern int pressure[2];
extern int gesture;
extern int speed;
extern ControlMode control_mode;
extern String finger_states;
extern const int pressure_max;

// Pin declarations
extern const int flexion_pins[5];
extern const int pinching_pins[5];
extern const int extension_pins[5];
extern const int abduction_pin;
extern const int adduction_pin;

void update_pressure() {
    // Skip if DAC is not available
    if (!mcp4728_available) {
        static unsigned long lastWarning = 0;
        if (millis() - lastWarning > 10000) { // Warn every 10 seconds
            Serial.println("Warning: DAC not available - skipping pressure update");
            lastWarning = millis();
        }
        return;
    }
    
    // Special handling: if gesture is 0 (all relax) in HTTP, SERIAL, and WIFI mode, 
    // set pressure to 0 regardless of user settings
    // ONLY in DATA_GLOVE mode, always use the actual pressure values
    int current_flexion = pressure[0];
    int current_extension = pressure[1];
    
    if (gesture == 0 && control_mode != DATA_GLOVE_MODE) {
        // When all relax and not in data glove mode, override to 0 pressure
        // This now applies to WiFi mode as well
        current_flexion = 0;
        current_extension = 0;
    }
    
    // Validate pressure values
    if (current_flexion < 0 || current_flexion > pressure_max || 
        current_extension < 0 || current_extension > pressure_max) {
        Serial.println("Error: Pressure should be between 0 - " + String(pressure_max));
        return;
    }
    
    // Calculate DAC values
    int dac_value_flexion = (current_flexion * 4095) / pressure_max;
    int dac_value_extension = (current_extension * 4095) / pressure_max;
    
    // Only output debug for significant changes (optimize performance)
    static int last_flex = -1, last_ext = -1;
    if (dac_value_flexion != last_flex || dac_value_extension != last_ext) {
        Serial.print("Setting DAC pressure values: Flexion=");
        Serial.print(dac_value_flexion);
        Serial.print(", Extension=");
        Serial.println(dac_value_extension);
        
        last_flex = dac_value_flexion;
        last_ext = dac_value_extension;
    }
    
    // Set DAC channels for pressure control
    dac.setChannelValue(MCP4728_CHANNEL_B, dac_value_flexion);
    dac.setChannelValue(MCP4728_CHANNEL_A, dac_value_extension);
}

void update_speed() {
    // Skip if DAC is not available
    if (!mcp4728_available) {
        static unsigned long lastWarning = 0;
        if (millis() - lastWarning > 10000) { // Warn every 10 seconds
            Serial.println("Warning: DAC not available - skipping speed update");
            lastWarning = millis();
        }
        return;
    }
    
    // Special handling: if gesture is 0 (all relax) in HTTP, SERIAL, and WIFI mode,
    // set speed to 0 regardless of user settings
    // ONLY in DATA_GLOVE mode, always use the actual speed value
    int current_speed = speed;
    
    if (gesture == 0 && control_mode != DATA_GLOVE_MODE) {
        // When all relax and not in data glove mode, override to 0 speed
        // This now applies to WiFi mode as well
        current_speed = 0;
    }
    
    // Only output debug for changes (optimize performance)
    static int last_speed = -1;
    if (current_speed != last_speed) {
        Serial.print("Setting speed level: ");
        Serial.println(current_speed);
        last_speed = current_speed;
    }
    
    // Calculate DAC values for speed control channels
    int valueC = 0;
    int valueD = 0;
    
    switch(current_speed) {
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
        default:
            Serial.println("Invalid speed value. Speed should be between 0-4.");
            return;
    }
    
    // Set speed control channels
    // Note: Channel assignment appears to be swapped (D for valueC, C for valueD)
    // This is maintained for compatibility with existing hardware
    dac.setChannelValue(MCP4728_CHANNEL_D, valueC);
    dac.setChannelValue(MCP4728_CHANNEL_C, valueD);
}

void update_hand_gesture() {
    // Optimized gesture mapping - only update if gesture changed
    static int last_gesture = -1;
    if (gesture == last_gesture) {
        return; // No change, skip update
    }
    last_gesture = gesture;
    
    // Map gestures to finger states
    switch(gesture) {
        case 0: // all relax
            finger_states = "000000";
            break;
        case 1: // all flexion  
            finger_states = "111111"; 
            break;
        case 2: // all extension
            finger_states = "222221"; 
            break;
        case 3: // 2 fingers pinch
            finger_states = "221111"; 
            break;
        case 4: // 3 fingers pinch 
            finger_states = "222111";  
            break;
        case 5: // thumb
            finger_states = "211110";  
            break;
        case 6: // index
            finger_states = "121111";  
            break;
        case 7: // middle
            finger_states = "112111";  
            break;
        case 8: // yeah
            finger_states = "122111";  
            break;
        default:
            // Invalid gesture, set to relax
            finger_states = "000000";
            Serial.print("Warning: Invalid gesture ");
            Serial.println(gesture);
            break;
    }
    
    update_finger_states();
}

void update_finger_states() {
    // Make sure finger_states has enough characters
    if (finger_states.length() < 6) {
        Serial.println("Error: finger_states string is too short");
        return;
    }
    
    // Validate finger_states string
    for (int i = 0; i < 6; i++) {
        char state = finger_states.charAt(i);
        if (state < '0' || state > '3') {
            Serial.print("Error: Invalid character in finger_states at position ");
            Serial.print(i);
            Serial.print(": ");
            Serial.println(state);
            return;
        }
    }
    
    // Optimized finger state updates - only change pins that need to change
    static String last_finger_states = "";
    
    // Loop through each finger (0-4) and set pins only if changed
    for (int i = 0; i < 5; i++) {
        char state = finger_states.charAt(i);
        char last_state = (i < last_finger_states.length()) ? last_finger_states.charAt(i) : 'X';
        
        // Only update if state changed
        if (state != last_state) {
            // Turn off all pins for this finger first
            digitalWrite(flexion_pins[i], LOW);
            digitalWrite(extension_pins[i], LOW);
            digitalWrite(pinching_pins[i], LOW);
            
            // Set the appropriate pin based on state
            switch(state) {
                case '1': // Flexion
                    digitalWrite(flexion_pins[i], HIGH);
                    break;
                case '2': // Extension
                    digitalWrite(extension_pins[i], HIGH);
                    break;
                case '3': // Pinching
                    digitalWrite(pinching_pins[i], HIGH);
                    break;
                case '0': // Relax - already set all LOW
                default:
                    break;
            }
        }
    }
    
    // Handle adduction/abduction (character at index 5)
    char adduction_state = finger_states.charAt(5);
    char last_adduction_state = (5 < last_finger_states.length()) ? last_finger_states.charAt(5) : 'X';
    
    // Only update if adduction state changed
    if (adduction_state != last_adduction_state) {
        switch(adduction_state) {
            case '0': // Relax
                digitalWrite(abduction_pin, LOW);
                digitalWrite(adduction_pin, LOW);
                break;
            case '1': // Adduction
                digitalWrite(abduction_pin, LOW);
                digitalWrite(adduction_pin, HIGH);
                break;
            case '2': // Abduction
                digitalWrite(abduction_pin, HIGH);
                digitalWrite(adduction_pin, LOW);
                break;
            default:
                digitalWrite(abduction_pin, LOW);
                digitalWrite(adduction_pin, LOW);
                break;
        }
    }
    
    // Update last state for next comparison
    last_finger_states = finger_states;
}