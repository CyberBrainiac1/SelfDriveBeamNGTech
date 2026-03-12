/*
 * ============================================================
 * SelfDriveBeamNGTech — Normal Mode Wheel Controller Firmware
 * Target: Arduino Leonardo (ATmega32U4)
 * Version: 1.0.0
 * ============================================================
 *
 * SECTION B — NORMAL DAILY-USE WHEEL FIRMWARE
 *
 * Hardware:
 *   - Arduino Leonardo
 *   - BTS7960 motor driver (RPWM, LPWM, R_EN, L_EN)
 *   - Quadrature encoder on steering shaft
 *   - Brushed DC motor
 *   - USB (HID + Serial via CDC)
 *
 * Modes:
 *   IDLE        — Motors off, listening for commands
 *   NORMAL_HID  — USB HID joystick/wheel mode
 *   ANGLE_TRACK — Follow a target angle from serial
 *   ASSIST      — Apply centering / FFB assist forces
 *   ESTOP       — Emergency stop, motors off, locked
 *   CALIBRATION — Encoder zeroing and range setup
 *
 * Serial Protocol (115200 baud, newline-terminated JSON-like):
 *   Commands sent TO Arduino:
 *     {"cmd":"set_mode","mode":"IDLE"}
 *     {"cmd":"set_mode","mode":"NORMAL_HID"}
 *     {"cmd":"set_mode","mode":"ANGLE_TRACK"}
 *     {"cmd":"set_mode","mode":"ASSIST"}
 *     {"cmd":"set_mode","mode":"ESTOP"}
 *     {"cmd":"set_mode","mode":"CALIBRATION"}
 *     {"cmd":"set_target","angle":<float>}        -- degrees, clamped to range
 *     {"cmd":"set_config","key":"<k>","value":<v>}
 *     {"cmd":"zero_encoder"}
 *     {"cmd":"set_center"}
 *     {"cmd":"estop"}
 *     {"cmd":"get_telemetry"}
 *     {"cmd":"ping"}
 *     {"cmd":"get_version"}
 *
 *   Telemetry sent FROM Arduino (every TELEM_INTERVAL_MS):
 *     {"type":"telem","angle":<f>,"target":<f>,"motor":<i>,
 *      "mode":"<s>","enc":<i>,"fault":<i>,"ts":<ul>}
 *
 * Safety:
 *   - Serial watchdog: if no command received in SERIAL_TIMEOUT_MS, ESTOP
 *   - Max motor output clamp: MAX_MOTOR_OUT (0-255)
 *   - Software angle clamps: ANGLE_MIN_DEG / ANGLE_MAX_DEG
 *   - Startup safe mode: begins in IDLE
 *   - Invalid commands ignored, fault flag set
 * ============================================================
 */

#include <Arduino.h>

// ---- USB HID (Leonardo) ----
// Uncomment for HID joystick output
// #include <Joystick.h>

// ============================================================
// CONFIG — Edit these to match your hardware
// ============================================================

// Encoder pins (interrupt-capable on Leonardo: 0,1,2,3)
#define ENC_A_PIN  2
#define ENC_B_PIN  3

// BTS7960 motor driver pins
#define MOTOR_RPWM  5   // Right (forward) PWM
#define MOTOR_LPWM  6   // Left (reverse) PWM
#define MOTOR_R_EN  7   // Right enable
#define MOTOR_L_EN  8   // Left enable

// Safety LED (optional)
#define LED_FAULT  13

// Control loop timing
#define CONTROL_INTERVAL_MS   10    // 100 Hz control loop
#define TELEM_INTERVAL_MS     50    // 20 Hz telemetry output
#define SERIAL_TIMEOUT_MS   2000    // 2s watchdog → ESTOP
#define STARTUP_SETTLE_MS    500    // delay before enabling output

// Angle / motion limits
#define ANGLE_MIN_DEG       -540.0f
#define ANGLE_MAX_DEG        540.0f
#define MAX_MOTOR_OUT          200  // 0–255, hardware safety ceiling
#define COUNTS_PER_REV        2400  // Encoder CPR (4× quadrature typical)
#define GEAR_RATIO             1.0f // Motor-to-shaft gear ratio

// PD controller gains (tune for your motor/inertia)
#define KP   1.8f
#define KD   0.12f
#define KI   0.0f   // Keep 0.0 unless you need steady-state correction

// Centering / assist strength (used in ASSIST mode)
#define ASSIST_CENTER_GAIN  0.8f
#define ASSIST_DAMPING      0.05f

// ============================================================
// MODE ENUM
// ============================================================
enum WheelMode {
    MODE_IDLE        = 0,
    MODE_NORMAL_HID  = 1,
    MODE_ANGLE_TRACK = 2,
    MODE_ASSIST      = 3,
    MODE_ESTOP       = 4,
    MODE_CALIBRATION = 5
};

const char* MODE_NAMES[] = {
    "IDLE", "NORMAL_HID", "ANGLE_TRACK", "ASSIST", "ESTOP", "CALIBRATION"
};

// ============================================================
// FAULT FLAGS (bitmask)
// ============================================================
#define FAULT_NONE          0x00
#define FAULT_SERIAL_TIMEOUT 0x01
#define FAULT_ANGLE_CLAMP   0x02
#define FAULT_INVALID_CMD   0x04
#define FAULT_MOTOR_ESTOP   0x08
#define FAULT_ENC_NOISE     0x10

// ============================================================
// STATE VARIABLES
// ============================================================
volatile long encoderCounts = 0;   // Raw encoder count (ISR-updated)
volatile int  lastEncA = LOW;

WheelMode currentMode    = MODE_IDLE;
float currentAngle       = 0.0f;   // Degrees
float targetAngle        = 0.0f;   // Degrees
float angleCenter        = 0.0f;   // Center offset in degrees
float angleRange         = 540.0f; // ± range in degrees

int   motorOutput        = 0;      // Signed: positive = one dir, negative = other
uint8_t faultFlags       = FAULT_NONE;

// PD state
float prevError          = 0.0f;
float integralError      = 0.0f;

// Timing
unsigned long lastControlMs  = 0;
unsigned long lastTelemMs    = 0;
unsigned long lastCmdMs      = 0;   // Watchdog
unsigned long startupDoneMs  = 0;

// Serial command buffer
#define CMD_BUF_LEN 128
char cmdBuf[CMD_BUF_LEN];
uint8_t cmdBufPos = 0;

// Version
#define FW_VERSION "1.0.0"

// ============================================================
// ENCODER ISRs
// ============================================================
void IRAM_ATTR encISR_A() {
    int a = digitalRead(ENC_A_PIN);
    int b = digitalRead(ENC_B_PIN);
    if (a == HIGH) {
        encoderCounts += (b == LOW) ? 1 : -1;
    } else {
        encoderCounts += (b == HIGH) ? 1 : -1;
    }
}

void IRAM_ATTR encISR_B() {
    int a = digitalRead(ENC_A_PIN);
    int b = digitalRead(ENC_B_PIN);
    if (b == HIGH) {
        encoderCounts += (a == HIGH) ? 1 : -1;
    } else {
        encoderCounts += (a == LOW) ? 1 : -1;
    }
}

// ============================================================
// MOTOR CONTROL
// ============================================================
void motorStop() {
    analogWrite(MOTOR_RPWM, 0);
    analogWrite(MOTOR_LPWM, 0);
}

void motorSet(int power) {
    // Clamp to max
    power = constrain(power, -MAX_MOTOR_OUT, MAX_MOTOR_OUT);
    if (power > 0) {
        analogWrite(MOTOR_RPWM, power);
        analogWrite(MOTOR_LPWM, 0);
    } else if (power < 0) {
        analogWrite(MOTOR_RPWM, 0);
        analogWrite(MOTOR_LPWM, -power);
    } else {
        motorStop();
    }
    motorOutput = power;
}

// ============================================================
// ESTOP
// ============================================================
void triggerEStop(uint8_t reason) {
    motorStop();
    motorOutput = 0;
    currentMode = MODE_ESTOP;
    faultFlags |= reason;
    digitalWrite(LED_FAULT, HIGH);
    Serial.println(F("{\"type\":\"estop\",\"reason\":\"watchdog\"}"));
}

// ============================================================
// ANGLE CALCULATION
// ============================================================
float countsToAngle(long counts) {
    // Convert encoder counts to degrees
    float degreesPerCount = 360.0f / (COUNTS_PER_REV * GEAR_RATIO);
    return (float)counts * degreesPerCount;
}

float getAngle() {
    long c;
    noInterrupts();
    c = encoderCounts;
    interrupts();
    return countsToAngle(c) - angleCenter;
}

// ============================================================
// PD CONTROLLER
// ============================================================
int pdController(float current, float target, float dt) {
    float error = target - current;

    // Angle clamp check
    if (current < ANGLE_MIN_DEG || current > ANGLE_MAX_DEG) {
        faultFlags |= FAULT_ANGLE_CLAMP;
        // Drive back toward safe range
        error = constrain(current, ANGLE_MIN_DEG, ANGLE_MAX_DEG) - current;
    }

    float derivative = (dt > 0) ? (error - prevError) / dt : 0.0f;
    integralError   += error * dt;
    integralError    = constrain(integralError, -50.0f, 50.0f); // anti-windup

    float output = KP * error + KD * derivative + KI * integralError;
    prevError = error;

    return (int)constrain(output, -MAX_MOTOR_OUT, MAX_MOTOR_OUT);
}

// ============================================================
// TELEMETRY OUTPUT
// ============================================================
void sendTelemetry() {
    long enc;
    noInterrupts();
    enc = encoderCounts;
    interrupts();

    Serial.print(F("{\"type\":\"telem\","
                   "\"angle\":"));
    Serial.print(currentAngle, 2);
    Serial.print(F(",\"target\":"));
    Serial.print(targetAngle, 2);
    Serial.print(F(",\"motor\":"));
    Serial.print(motorOutput);
    Serial.print(F(",\"mode\":\""));
    Serial.print(MODE_NAMES[currentMode]);
    Serial.print(F("\",\"enc\":"));
    Serial.print(enc);
    Serial.print(F(",\"fault\":"));
    Serial.print(faultFlags);
    Serial.print(F(",\"ts\":"));
    Serial.print(millis());
    Serial.println(F("}"));
}

// ============================================================
// SIMPLE JSON KEY EXTRACTION
// Finds "key":value in buf.  value is copied into out (string or number as string).
// Returns true if found.
// ============================================================
bool jsonGetStr(const char* buf, const char* key, char* out, int outLen) {
    char search[32];
    snprintf(search, sizeof(search), "\"%s\":\"", key);
    const char* p = strstr(buf, search);
    if (!p) return false;
    p += strlen(search);
    int i = 0;
    while (*p && *p != '"' && i < outLen - 1) {
        out[i++] = *p++;
    }
    out[i] = '\0';
    return (i > 0);
}

bool jsonGetFloat(const char* buf, const char* key, float* out) {
    char search[32];
    snprintf(search, sizeof(search), "\"%s\":", key);
    const char* p = strstr(buf, search);
    if (!p) return false;
    p += strlen(search);
    *out = atof(p);
    return true;
}

// ============================================================
// COMMAND PARSER
// ============================================================
void handleCommand(const char* buf) {
    char cmd[32] = "";
    if (!jsonGetStr(buf, "cmd", cmd, sizeof(cmd))) {
        faultFlags |= FAULT_INVALID_CMD;
        Serial.println(F("{\"type\":\"err\",\"msg\":\"no cmd\"}"));
        return;
    }

    // PING
    if (strcmp(cmd, "ping") == 0) {
        Serial.println(F("{\"type\":\"pong\"}"));
        return;
    }

    // VERSION
    if (strcmp(cmd, "get_version") == 0) {
        Serial.print(F("{\"type\":\"version\",\"fw\":\""));
        Serial.print(FW_VERSION);
        Serial.println(F("\"}"));
        return;
    }

    // ESTOP
    if (strcmp(cmd, "estop") == 0) {
        triggerEStop(FAULT_MOTOR_ESTOP);
        return;
    }

    // RESET FAULTS / IDLE
    if (strcmp(cmd, "clear_faults") == 0) {
        faultFlags = FAULT_NONE;
        currentMode = MODE_IDLE;
        motorStop();
        digitalWrite(LED_FAULT, LOW);
        Serial.println(F("{\"type\":\"ok\",\"msg\":\"faults cleared\"}"));
        return;
    }

    // SET MODE
    if (strcmp(cmd, "set_mode") == 0) {
        char modeStr[24] = "";
        jsonGetStr(buf, "mode", modeStr, sizeof(modeStr));

        if      (strcmp(modeStr, "IDLE")        == 0) { currentMode = MODE_IDLE;        motorStop(); }
        else if (strcmp(modeStr, "NORMAL_HID")  == 0) { currentMode = MODE_NORMAL_HID;  }
        else if (strcmp(modeStr, "ANGLE_TRACK") == 0) { currentMode = MODE_ANGLE_TRACK; integralError = 0; prevError = 0; }
        else if (strcmp(modeStr, "ASSIST")      == 0) { currentMode = MODE_ASSIST;      integralError = 0; prevError = 0; }
        else if (strcmp(modeStr, "ESTOP")       == 0) { triggerEStop(FAULT_MOTOR_ESTOP); return; }
        else if (strcmp(modeStr, "CALIBRATION") == 0) { currentMode = MODE_CALIBRATION; motorStop(); }
        else {
            faultFlags |= FAULT_INVALID_CMD;
            Serial.println(F("{\"type\":\"err\",\"msg\":\"unknown mode\"}"));
            return;
        }
        Serial.print(F("{\"type\":\"ok\",\"mode\":\""));
        Serial.print(modeStr);
        Serial.println(F("\"}"));
        return;
    }

    // SET TARGET ANGLE
    if (strcmp(cmd, "set_target") == 0) {
        float ang = 0.0f;
        jsonGetFloat(buf, "angle", &ang);
        ang = constrain(ang, ANGLE_MIN_DEG, ANGLE_MAX_DEG);
        targetAngle = ang;
        Serial.print(F("{\"type\":\"ok\",\"target\":"));
        Serial.print(targetAngle, 2);
        Serial.println(F("}"));
        return;
    }

    // ZERO ENCODER
    if (strcmp(cmd, "zero_encoder") == 0) {
        noInterrupts();
        encoderCounts = 0;
        interrupts();
        angleCenter  = 0.0f;
        currentAngle = 0.0f;
        targetAngle  = 0.0f;
        Serial.println(F("{\"type\":\"ok\",\"msg\":\"encoder zeroed\"}"));
        return;
    }

    // SET CENTER (current position = 0)
    if (strcmp(cmd, "set_center") == 0) {
        noInterrupts();
        encoderCounts = 0;
        interrupts();
        angleCenter  = 0.0f;
        currentAngle = 0.0f;
        targetAngle  = 0.0f;
        Serial.println(F("{\"type\":\"ok\",\"msg\":\"center set\"}"));
        return;
    }

    // GET TELEMETRY ON DEMAND
    if (strcmp(cmd, "get_telemetry") == 0) {
        sendTelemetry();
        return;
    }

    // SET CONFIG
    if (strcmp(cmd, "set_config") == 0) {
        char key[24] = "";
        jsonGetStr(buf, "key", key, sizeof(key));
        float val = 0.0f;
        jsonGetFloat(buf, "value", &val);

        if      (strcmp(key, "angle_range")  == 0) angleRange = constrain(val, 90.0f, 1080.0f);
        else if (strcmp(key, "max_motor")    == 0) { /* handled at compile time — runtime clamp note */ }
        else {
            faultFlags |= FAULT_INVALID_CMD;
            Serial.println(F("{\"type\":\"err\",\"msg\":\"unknown config key\"}"));
            return;
        }
        Serial.print(F("{\"type\":\"ok\",\"key\":\""));
        Serial.print(key);
        Serial.print(F("\",\"value\":"));
        Serial.print(val, 2);
        Serial.println(F("}"));
        return;
    }

    // Unknown command
    faultFlags |= FAULT_INVALID_CMD;
    Serial.print(F("{\"type\":\"err\",\"msg\":\"unknown cmd: "));
    Serial.print(cmd);
    Serial.println(F("\"}"));
}

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);

    // Encoder pins
    pinMode(ENC_A_PIN, INPUT_PULLUP);
    pinMode(ENC_B_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ENC_A_PIN), encISR_A, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_B_PIN), encISR_B, CHANGE);

    // Motor driver pins
    pinMode(MOTOR_RPWM, OUTPUT);
    pinMode(MOTOR_LPWM, OUTPUT);
    pinMode(MOTOR_R_EN, OUTPUT);
    pinMode(MOTOR_L_EN, OUTPUT);
    digitalWrite(MOTOR_R_EN, HIGH);
    digitalWrite(MOTOR_L_EN, HIGH);
    motorStop();

    // LED
    pinMode(LED_FAULT, OUTPUT);
    digitalWrite(LED_FAULT, LOW);

    // Startup settle
    delay(STARTUP_SETTLE_MS);
    startupDoneMs = millis();
    lastCmdMs     = millis();

    // Ready message
    Serial.print(F("{\"type\":\"ready\",\"fw\":\""));
    Serial.print(FW_VERSION);
    Serial.println(F("\",\"mode\":\"IDLE\"}"));
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
    unsigned long now = millis();

    // ---- Read serial input (non-blocking) ----
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdBufPos > 0) {
                cmdBuf[cmdBufPos] = '\0';
                lastCmdMs = now;   // Reset watchdog
                handleCommand(cmdBuf);
                cmdBufPos = 0;
            }
        } else if (cmdBufPos < CMD_BUF_LEN - 1) {
            cmdBuf[cmdBufPos++] = c;
        }
    }

    // ---- Serial watchdog (skip during ESTOP and CALIBRATION) ----
    if (currentMode != MODE_ESTOP && currentMode != MODE_IDLE &&
        currentMode != MODE_CALIBRATION) {
        if ((now - lastCmdMs) > SERIAL_TIMEOUT_MS) {
            triggerEStop(FAULT_SERIAL_TIMEOUT);
        }
    }

    // ---- Control loop (100 Hz) ----
    if ((now - lastControlMs) >= CONTROL_INTERVAL_MS) {
        float dt = (now - lastControlMs) / 1000.0f;
        lastControlMs = now;

        currentAngle = getAngle();

        switch (currentMode) {

            case MODE_IDLE:
                motorStop();
                motorOutput = 0;
                break;

            case MODE_ESTOP:
                motorStop();
                motorOutput = 0;
                break;

            case MODE_NORMAL_HID:
                // In HID mode, motor control is via FFB effects (future expansion)
                // For now: hold position with light centering
                {
                    int out = pdController(currentAngle, 0.0f, dt);
                    out = (int)((float)out * ASSIST_CENTER_GAIN * 0.3f); // Light center assist
                    motorSet(out);
                }
                break;

            case MODE_ANGLE_TRACK:
                // Follow targetAngle using PD controller
                {
                    int out = pdController(currentAngle, targetAngle, dt);
                    motorSet(out);
                }
                break;

            case MODE_ASSIST:
                // Centering + damping assist
                {
                    int center_out = (int)(KP * ASSIST_CENTER_GAIN * (0.0f - currentAngle));
                    motorSet(constrain(center_out, -MAX_MOTOR_OUT, MAX_MOTOR_OUT));
                }
                break;

            case MODE_CALIBRATION:
                // Motors off in calibration
                motorStop();
                motorOutput = 0;
                break;
        }
    }

    // ---- Telemetry output (20 Hz) ----
    if ((now - lastTelemMs) >= TELEM_INTERVAL_MS) {
        lastTelemMs = now;
        sendTelemetry();
    }
}
