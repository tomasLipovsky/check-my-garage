/*
 * Garage Door Monitor - Arduino Nano
 * Reads two switch sensors and sends readings to Python via Serial
 * 
 * Output format: "open_sensor,closed_sensor\n"
 * Example: "1,0" means open sensor triggered (1), closed sensor not triggered (0)
 */

// ==================== PIN CONFIGURATION ====================

const int FULLY_OPEN_PIN = 2;      // Digital pin for fully open sensor
const int FULLY_CLOSED_PIN = 3;    // Digital pin for fully closed sensor
const int LED_PIN = LED_BUILTIN;   // Status LED

// ==================== CONFIGURATION ====================

const long BAUD_RATE = 9600;           // Serial communication speed (must match Python)
const unsigned long UPDATE_INTERVAL = 500;  // Send update every 500ms
const int DEBOUNCE_READS = 5;          // Number of readings for debouncing
const int DEBOUNCE_DELAY = 10;         // Delay between debounce reads (ms)

// IR sensors: LOW when object detected, HIGH when no object
const int SENSOR_TRIGGERED_STATE = LOW;

// ==================== GLOBAL VARIABLES ====================

int lastOpenState = -1;           // Last reported open sensor state
int lastClosedState = -1;         // Last reported closed sensor state
unsigned long lastUpdateTime = 0; // Time of last update

// ==================== SETUP ====================

void setup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  
  // Configure pins (INPUT mode for IR sensors with external power)
  pinMode(FULLY_OPEN_PIN, INPUT);
  pinMode(FULLY_CLOSED_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  
  // Wait for serial connection to stabilize
  delay(1000);
  
  // Flash LED to indicate Arduino is ready
  for(int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(150);
    digitalWrite(LED_PIN, LOW);
    delay(150);
  }
  
  // Send initial reading
  readAndSendState();
}

// ==================== MAIN LOOP ====================

void loop() {
  unsigned long currentTime = millis();
  
  // Send periodic updates
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    readAndSendState();
    lastUpdateTime = currentTime;
  }
  
  delay(10);  // Small delay for stability
}

// ==================== FUNCTIONS ====================

/**
 * Read sensor states with debouncing and send via serial
 */
void readAndSendState() {
  // Read both sensors with debouncing
  int openState = readSensorDebounced(FULLY_OPEN_PIN);
  int closedState = readSensorDebounced(FULLY_CLOSED_PIN);
  
  // Convert to triggered/not-triggered format
  int openValue = (openState == SENSOR_TRIGGERED_STATE) ? 1 : 0;
  int closedValue = (closedState == SENSOR_TRIGGERED_STATE) ? 1 : 0;
  
  // Send state via serial in format: "open,closed"
  Serial.print(openValue);
  Serial.print(",");
  Serial.println(closedValue);
  
  // Update LED to indicate activity
  if (openValue != lastOpenState || closedValue != lastClosedState) {
    // Blink LED on state change
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    
    lastOpenState = openValue;
    lastClosedState = closedValue;
  }
}

/**
 * Read sensor with debouncing
 * Takes multiple readings and returns the most common value
 */
int readSensorDebounced(int pin) {
  int highCount = 0;
  int lowCount = 0;
  
  // Take multiple readings
  for (int i = 0; i < DEBOUNCE_READS; i++) {
    int reading = digitalRead(pin);
    if (reading == HIGH) {
      highCount++;
    } else {
      lowCount++;
    }
    delay(DEBOUNCE_DELAY);
  }
  
  // Return the most common reading
  return (highCount > lowCount) ? HIGH : LOW;
}