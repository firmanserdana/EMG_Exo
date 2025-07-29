// External variable declarations
extern int gesture;
extern int pressure[2];
extern int speed;
extern int data_glove;
extern ControlMode control_mode;
extern String finger_states;
extern bool data_glove_initialized;
extern bool mcp4728_available;

// External function declarations
bool init_dac();
void update_pressure();
void update_speed();
void init_data_glove();
void init_wifi_direct();

void serial_read_state() {
    if (Serial.available() > 0) {
        char command = Serial.read();
        if (command == 'p') {
            // Read pressure values
            pressure[0] = Serial.parseInt();
            pressure[1] = Serial.parseInt();
            
            // Validate pressure values
            if (pressure[0] < 0 || pressure[0] > 100 || pressure[1] < 0 || pressure[1] > 100) {
                Serial.println("Error: Pressure values must be between 0-100");
                return;
            }
            
            Serial.print("Set Pressure: ");
            Serial.print(pressure[0]);
            Serial.print(", ");
            Serial.println(pressure[1]);
            
            // Initialize DAC if needed and update pressure
            if (init_dac()) {
                update_pressure();
            }
        } else if (command == 's') {
            // Read speed value
            speed = Serial.parseInt();
            
            // Validate speed value
            if (speed < 0 || speed > 4) {
                Serial.println("Error: Speed must be between 0-4");
                return;
            }
            
            Serial.print("Set Speed Level: ");
            Serial.println(speed);
            
            // Initialize DAC if needed and update speed
            if (init_dac()) {
                update_speed();
            }
        } else if (command == 'g') {
            // Read gesture value
            int new_gesture = Serial.parseInt();
            
            // Validate gesture value
            if (new_gesture < 0 || new_gesture > 8) {
                Serial.println("Error: Gesture must be between 0-8");
                return;
            }
            
            Serial.print("Set Gesture: ");
            Serial.println(new_gesture);
            
            // Update the gesture
            gesture = new_gesture;
            
            // If gesture is set to 0 (relax) and not in data glove mode,
            // update pressure and speed to 0 (this now includes WiFi mode)
            if (gesture == 0 && control_mode != DATA_GLOVE_MODE && init_dac()) {
                Serial.println("Gesture set to RELAX (non-data-glove mode), automatically setting pressure and speed to 0");
                update_pressure();
                update_speed();
            }
        } else if (command == 'd') {
            // Read data glove command
            String input = Serial.readString(); 
            input.trim();  

            if (input == "on") {
                Serial.println("Data Glove ON");
                data_glove = 1;
                control_mode = DATA_GLOVE_MODE;
                
                // Initialize data glove if needed
                if (!data_glove_initialized) {
                    init_data_glove();
                }
                
                // Make sure DAC is initialized for pressure and speed in Data Glove mode
                init_dac();
            }
            else if (input == "off") {
                Serial.println("Data Glove OFF");
                data_glove = 0;
                control_mode = SERIAL_MODE;
                
                // Initialize DAC when switching to Serial mode
                init_dac();
            }
            else {
                Serial.println("Invalid command, use 'd on' or 'd off'");
            }
        } else if (command == 'w') {
            // Read WiFi control command
            String input = Serial.readString(); 
            input.trim();  

            if (input == "on") {
                Serial.println("WiFi Control ON");
                data_glove = 0;
                control_mode = WIFI_MODE;
                
                // Initialize WiFi direct control
                init_wifi_direct();
                
                // Make sure DAC is initialized for pressure and speed in WiFi mode
                init_dac();
                
                Serial.println("UDP server ready on port 4210");
            }
            else if (input == "off") {
                Serial.println("WiFi Control OFF");
                control_mode = SERIAL_MODE;
                
                // Initialize DAC when switching to Serial mode
                init_dac();
            }
            else {
                Serial.println("Invalid command, use 'w on' or 'w off'");
            }
        } else if (command == 'm') {
            // Read mode value
            int mode = Serial.parseInt();
            
            if (mode == 0) {
                control_mode = HTTP_MODE;
                data_glove = 0;
                Serial.println("Mode set to HTTP");
                
                // Initialize DAC for HTTP mode
                init_dac();
            } else if (mode == 1) {
                control_mode = SERIAL_MODE;
                data_glove = 0;
                Serial.println("Mode set to Serial");
                
                // Initialize DAC for Serial mode
                init_dac();
            } else if (mode == 2) {
                control_mode = DATA_GLOVE_MODE;
                data_glove = 1;
                
                // Initialize data glove if needed
                if (!data_glove_initialized) {
                    init_data_glove();
                }
                
                // Initialize DAC for pressure and speed in Data Glove mode
                init_dac();
                
                Serial.println("Mode set to Data Glove");
            } else if (mode == 3) {
                control_mode = WIFI_MODE;
                data_glove = 0;
                
                // Initialize WiFi direct control
                init_wifi_direct();
                
                // Initialize DAC for pressure and speed in WiFi mode
                init_dac();
                
                Serial.println("Mode set to WiFi Control");
                Serial.println("UDP server ready on port 4210");
            } else {
                Serial.println("Invalid mode, use 0 (HTTP), 1 (Serial), 2 (Data Glove), or 3 (WiFi Control)");
            }
        } 
        // Add test command
        else if (command == 't') {
            Serial.println("Testing dual channel operation...");
            
            if (init_dac()) {
                // Import DAC object
                extern Adafruit_MCP4728 dac;
                
                // First set both channels to 0
                dac.setChannelValue(MCP4728_CHANNEL_C, 0);
                dac.setChannelValue(MCP4728_CHANNEL_D, 0);
                delay(1000);
                
                // Test 1: Set channels to medium value with delay
                Serial.println("Test 1: Setting both channels to 2048 (with delay)");
                dac.setChannelValue(MCP4728_CHANNEL_C, 2048);
                delay(10); // Short delay
                dac.setChannelValue(MCP4728_CHANNEL_D, 2048);
                delay(5000);
                
                // Turn off both channels
                Serial.println("Turning off both channels");
                dac.setChannelValue(MCP4728_CHANNEL_C, 0);
                delay(10);
                dac.setChannelValue(MCP4728_CHANNEL_D, 0);
                delay(1000);
                
                // Test 2: Same settings but with longer delay
                Serial.println("Test 2: Setting both channels to 2048 (with longer delay)");
                dac.setChannelValue(MCP4728_CHANNEL_C, 2048);
                delay(50); // Longer delay
                dac.setChannelValue(MCP4728_CHANNEL_D, 2048);
                delay(5000);
                
                // Turn off both channels
                Serial.println("Turning off both channels");
                dac.setChannelValue(MCP4728_CHANNEL_C, 0);
                delay(50);
                dac.setChannelValue(MCP4728_CHANNEL_D, 0);
                delay(1000);
                
                // Test 3: Set channels to maximum value
                Serial.println("Test 3: Setting both channels to 4095");
                dac.setChannelValue(MCP4728_CHANNEL_C, 4095);
                delay(50);
                dac.setChannelValue(MCP4728_CHANNEL_D, 4095);
                delay(5000);
                
                // Turn off both channels
                Serial.println("Test complete, turning off both channels");
                dac.setChannelValue(MCP4728_CHANNEL_C, 0);
                delay(50);
                dac.setChannelValue(MCP4728_CHANNEL_D, 0);
            } else {
                Serial.println("Error: DAC not available for testing");
            }
        }
        else if (command == 'h') {
            // Help command
            Serial.println("\n=== ESP32 Glove Control Commands ===");
            Serial.println("p [flex] [ext] - Set pressure (0-100)");
            Serial.println("s [speed] - Set speed level (0-4)");
            Serial.println("g [gesture] - Set gesture (0-8)");
            Serial.println("m [mode] - Set mode: 0=HTTP, 1=Serial, 2=DataGlove, 3=WiFi");
            Serial.println("d on/off - Data glove control");
            Serial.println("w on/off - WiFi control mode");
            Serial.println("t - Test DAC channels");
            Serial.println("h - Show this help");
            Serial.println("=====================================\n");
        }
        else {
            // Clear any remaining characters in the buffer
            while (Serial.available() > 0) {
                Serial.read();
            }
            Serial.println("Unknown command. Type 'h' for help.");
        }
    }
}