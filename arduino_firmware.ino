/*
 =============================================================================
 Industrial Edge RTU Firmware (Arduino Uno)
 Telemetry Acquisition, Safety Containment Actuation & SCADA Bridge Interface
 =============================================================================
*/

// --- PIN DEFINITIONS ---
const int PIN_GAS_ANALOG    = A0;  // Gas Sensor (MQ-2 / MQ-135 / MQ-7) Analog Input
const int PIN_VALVE_RELAY   = 8;   // Solenoid / Isolation Valve Relay (or Status LED)
const int PIN_FAN_RELAY     = 9;   // Ventilation Extraction Fan Relay (or Status LED)
const int PIN_BUZZER_ALARM  = 6;   // Auditory Piezo Alarm Buzzer

// --- TIMING & TELEMETRY PARAMETERS ---
const unsigned long TELEMETRY_INTERVAL_MS = 1000;
unsigned long lastTelemetryTimestamp = 0;

// Current Actuator States
bool valveOpen = true;
bool fanOn = false;

void setup() {
  // Initialize High-Speed Hardware UART
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port connection
  }

  // Actuator I/O Direction
  pinMode(PIN_VALVE_RELAY, OUTPUT);
  pinMode(PIN_FAN_RELAY, OUTPUT);
  pinMode(PIN_BUZZER_ALARM, OUTPUT);

  // Default Initial Safety Envelope: Valve OPEN, Fan OFF, Alarm OFF
  digitalWrite(PIN_VALVE_RELAY, LOW);   // LOW = Valve OPEN (Normal Flow)
  digitalWrite(PIN_FAN_RELAY, LOW);     // LOW = Fan OFF
  digitalWrite(PIN_BUZZER_ALARM, LOW);  // LOW = Buzzer OFF

  Serial.println("SCADA_RTU_ONLINE");
}

void loop() {
  unsigned long currentMillis = millis();

  // 1. DISPATCH PERIODIC PPM TELEMETRY (Every 1000ms)
  if (currentMillis - lastTelemetryTimestamp >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTimestamp = currentMillis;

    // Read analog sensor sample (0 - 1023)
    int rawAdc = analogRead(PIN_GAS_ANALOG);

    // Dynamic industrial calibration curve (scaling ADC to ~100 - 1500 PPM)
    int ppm = map(rawAdc, 50, 950, 150, 1500);
    if (ppm < 100) ppm = 100;

    // Dispatch raw integer value across serial bus to bridge.py
    Serial.println(ppm);

    // Autonomous Hardware-Level Emergency Backup Interlock
    if (ppm > 1000) {
      // Local fail-safe even if computer/bridge loses connection
      digitalWrite(PIN_BUZZER_ALARM, HIGH);
    } else {
      digitalWrite(PIN_BUZZER_ALARM, LOW);
    }
  }

  // 2. PROCESS SUPERVISORY COMMANDS FROM SCADA CLOUD BRIDGE
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "VALVE_OPEN") {
      valveOpen = true;
      digitalWrite(PIN_VALVE_RELAY, LOW); // OPEN
    } 
    else if (command == "VALVE_CLOSED") {
      valveOpen = false;
      digitalWrite(PIN_VALVE_RELAY, HIGH); // EMERGENCY SHUTOFF
    } 
    else if (command == "FAN_ON") {
      fanOn = true;
      digitalWrite(PIN_FAN_RELAY, HIGH); // START EXTRACTION
    } 
    else if (command == "FAN_OFF") {
      fanOn = false;
      digitalWrite(PIN_FAN_RELAY, LOW); // STOP EXTRACTION
    }
  }
}
