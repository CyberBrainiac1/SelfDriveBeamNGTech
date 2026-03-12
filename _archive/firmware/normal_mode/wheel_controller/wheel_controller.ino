/*
 * wheel_controller.ino — SelfDriveBeamNGTech Normal Wheel Firmware
 * Target: Arduino Leonardo (ATmega32U4)
 * Version: 2.0.0
 *
 * ── WHAT THIS FIRMWARE DOES ─────────────────────────────────────
 *  • Reads a quadrature encoder on the steering shaft
 *  • Calculates real-time steering angle
 *  • Controls a brushed DC motor via BTS7960 driver
 *  • Runs a PD controller to follow a target angle
 *  • Applies FFB effects: centering spring, damper, friction, inertia
 *  • Persists all settings in EEPROM (survives power cycles)
 *  • Supports 4 named EEPROM profile slots
 *  • Sends JSON telemetry over serial
 *  • Receives JSON commands over serial
 *  • Exposes USB HID joystick axis for the steering wheel
 *
 * ── EEPROM LAYOUT ────────────────────────────────────────────────
 *  Addr 0x000 : uint32_t magic  (0xABCD1234 = valid data flag)
 *  Addr 0x004 : WheelConfig     active config  (~56 bytes)
 *  Addr 0x040 : ProfileSlot[4]  named profiles (~76 bytes each)
 *  Total used : ~352 of 1024 bytes
 *
 * ── PIN ASSIGNMENTS ──────────────────────────────────────────────
 *  Encoder A  → pin 2  (INT0 / hardware interrupt)
 *  Encoder B  → pin 3  (INT1 / hardware interrupt)
 *  BTS7960 RPWM  → pin 9   (right / positive direction PWM)
 *  BTS7960 LPWM  → pin 10  (left  / negative direction PWM)
 *  BTS7960 R_EN  → pin 7
 *  BTS7960 L_EN  → pin 8
 *  Status LED    → pin 13 (built-in)
 *
 * ── SERIAL PROTOCOL ──────────────────────────────────────────────
 *  All messages are single-line JSON terminated with '\n'.
 *  Commands (PC → Arduino):
 *    {"cmd":"set_mode","mode":"IDLE"}
 *    {"cmd":"set_target","angle":45.0}
 *    {"cmd":"set_config","key":"kp","value":1.8}
 *    {"cmd":"get_config"}
 *    {"cmd":"save_config"}
 *    {"cmd":"load_config"}
 *    {"cmd":"save_profile","slot":0,"name":"Normal"}
 *    {"cmd":"load_profile","slot":0}
 *    {"cmd":"list_profiles"}
 *    {"cmd":"factory_reset"}
 *    {"cmd":"zero_encoder"}
 *    {"cmd":"set_center"}
 *    {"cmd":"motor_test","dir":1,"pwm":80}
 *    {"cmd":"ping"}
 *    {"cmd":"get_version"}
 *    {"cmd":"clear_faults"}
 *    {"cmd":"estop"}
 *
 *  Telemetry (Arduino → PC, ~50 Hz):
 *    {"t":"telem","angle":0.0,"target":0.0,"motor":0,"mode":"IDLE",
 *     "enc":0,"vel":0.0,"fault":0,"profile":"Default","uptime":1234}
 *
 * ── SAFETY ───────────────────────────────────────────────────────
 *  - Motor off at boot until commanded
 *  - Serial timeout: motor off if no command for SERIAL_TIMEOUT_MS
 *  - Hard angle clamp in ANGLE_TRACK/ASSIST modes
 *  - Max PWM ceiling enforced in all modes
 *  - ESTOP command instantly kills motor and locks out
 *  - ESTOP cleared only by explicit set_mode command
 */

#include <EEPROM.h>
#include <ArduinoJson.h>
// Note: HID.h / Joystick.h optional — include if using USB HID axis output.
// Uncomment the line below if you have the Joystick library installed:
// #include <Joystick.h>

// ═══════════════════════════════════════════════════════════════════
//  CONSTANTS & PIN DEFINITIONS
// ═══════════════════════════════════════════════════════════════════

#define FW_VERSION     "2.0.0"
#define SERIAL_BAUD    115200
#define TELEM_RATE_MS  20          // ~50 Hz telemetry
#define CMD_BUFFER_LEN 256
#define SERIAL_TIMEOUT_MS 500      // motor off if silent this long (ms)
#define EEPROM_MAGIC   0xABCD1234UL
#define EEPROM_ADDR_MAGIC   0
#define EEPROM_ADDR_CONFIG  4
#define EEPROM_ADDR_PROFILES 64    // 4 × ~76 bytes = 304 bytes → ends at 368

#define PIN_ENC_A    2   // interrupt 0
#define PIN_ENC_B    3   // interrupt 1
#define PIN_RPWM     9
#define PIN_LPWM     10
#define PIN_R_EN     7
#define PIN_L_EN     8
#define PIN_LED      13

#define NUM_PROFILES 4
#define PROFILE_NAME_LEN 16

// ═══════════════════════════════════════════════════════════════════
//  DATA STRUCTURES
// ═══════════════════════════════════════════════════════════════════

/* All tunable wheel parameters — stored in EEPROM as one block. */
struct WheelConfig {
  // PD controller
  float kp;             // proportional gain          (default 1.8)
  float kd;             // derivative gain             (default 0.12)
  float ki;             // integral gain (use sparingly, default 0.0)
  float dead_zone;      // degrees — no output inside  (default 1.5)

  // Angle / encoder
  float angle_range;    // total rotation degrees      (default 540.0)
  float counts_per_rev; // encoder counts per shaft rev (default 2400.0)
  float gear_ratio;     // motor-to-shaft ratio         (default 1.0)
  bool  invert_encoder; // flip encoder direction       (default false)
  bool  invert_motor;   // flip motor direction         (default false)

  // Motor limits
  uint8_t max_motor;    // PWM ceiling 0–255           (default 200)
  float   slew_rate;    // max PWM change per loop (0=off, default 20)

  // FFB effects (NORMAL_HID / ASSIST modes)
  float centering;      // spring center strength 0–3  (default 1.0)
  float damping;        // velocity-proportional brake (default 0.12)
  float friction;       // constant resistance 0–1     (default 0.05)
  float inertia;        // acceleration resistance 0–1 (default 0.04)
  float smoothing;      // output LP filter 0–1        (default 0.10)
};

/* One named preset stored in EEPROM. */
struct ProfileSlot {
  char        name[PROFILE_NAME_LEN];
  WheelConfig config;
  uint8_t     valid;   // 0xAA = has valid data
};

// ═══════════════════════════════════════════════════════════════════
//  DEFAULTS
// ═══════════════════════════════════════════════════════════════════

WheelConfig defaultConfig() {
  WheelConfig c;
  c.kp             = 1.8f;
  c.kd             = 0.12f;
  c.ki             = 0.0f;
  c.dead_zone      = 1.5f;
  c.angle_range    = 540.0f;
  c.counts_per_rev = 2400.0f;
  c.gear_ratio     = 1.0f;
  c.invert_encoder = false;
  c.invert_motor   = false;
  c.max_motor      = 200;
  c.slew_rate      = 20.0f;
  c.centering      = 1.0f;
  c.damping        = 0.12f;
  c.friction       = 0.05f;
  c.inertia        = 0.04f;
  c.smoothing      = 0.10f;
  return c;
}

// ═══════════════════════════════════════════════════════════════════
//  EEPROM HELPERS
// ═══════════════════════════════════════════════════════════════════

void eeprom_write_config(const WheelConfig &cfg) {
  EEPROM.put(EEPROM_ADDR_CONFIG, cfg);
}

void eeprom_read_config(WheelConfig &cfg) {
  EEPROM.get(EEPROM_ADDR_CONFIG, cfg);
}

void eeprom_write_magic() {
  uint32_t magic = EEPROM_MAGIC;
  EEPROM.put(EEPROM_ADDR_MAGIC, magic);
}

bool eeprom_is_valid() {
  uint32_t magic;
  EEPROM.get(EEPROM_ADDR_MAGIC, magic);
  return (magic == EEPROM_MAGIC);
}

void eeprom_write_profile(uint8_t slot, const ProfileSlot &ps) {
  if (slot >= NUM_PROFILES) return;
  EEPROM.put(EEPROM_ADDR_PROFILES + slot * sizeof(ProfileSlot), ps);
}

void eeprom_read_profile(uint8_t slot, ProfileSlot &ps) {
  if (slot >= NUM_PROFILES) return;
  EEPROM.get(EEPROM_ADDR_PROFILES + slot * sizeof(ProfileSlot), ps);
}

void eeprom_factory_reset() {
  // Overwrite magic to invalidate, then write defaults
  uint32_t zero = 0;
  EEPROM.put(EEPROM_ADDR_MAGIC, zero);
  WheelConfig def = defaultConfig();
  eeprom_write_config(def);
  eeprom_write_magic();
  // Clear profile slots
  ProfileSlot blank;
  blank.valid = 0x00;
  memset(blank.name, 0, PROFILE_NAME_LEN);
  for (uint8_t i = 0; i < NUM_PROFILES; i++) {
    eeprom_write_profile(i, blank);
  }
}

// ═══════════════════════════════════════════════════════════════════
//  ENCODER (interrupt-driven quadrature)
// ═══════════════════════════════════════════════════════════════════

volatile long enc_count = 0;
int8_t last_enc_state   = 0;

void enc_isr_a() {
  int8_t a = digitalRead(PIN_ENC_A);
  int8_t b = digitalRead(PIN_ENC_B);
  int8_t state = (a << 1) | b;
  // Standard quadrature decode table
  static const int8_t table[16] = {
     0, -1,  1,  0,
     1,  0,  0, -1,
    -1,  0,  0,  1,
     0,  1, -1,  0
  };
  enc_count += table[(last_enc_state << 2) | state];
  last_enc_state = state;
}

void enc_isr_b() { enc_isr_a(); }

// ═══════════════════════════════════════════════════════════════════
//  MOTOR DRIVER (BTS7960)
// ═══════════════════════════════════════════════════════════════════

void motor_enable(bool en) {
  digitalWrite(PIN_R_EN, en ? HIGH : LOW);
  digitalWrite(PIN_L_EN, en ? HIGH : LOW);
}

/* Drive motor: output = -255..+255. Positive = forward direction. */
void motor_drive(int output, bool invert) {
  if (invert) output = -output;
  output = constrain(output, -255, 255);
  if (output > 0) {
    analogWrite(PIN_RPWM, output);
    analogWrite(PIN_LPWM, 0);
  } else if (output < 0) {
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, -output);
  } else {
    analogWrite(PIN_RPWM, 0);
    analogWrite(PIN_LPWM, 0);
  }
}

void motor_stop() {
  analogWrite(PIN_RPWM, 0);
  analogWrite(PIN_LPWM, 0);
}

// ═══════════════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════════════

// Modes
#define MODE_IDLE        0
#define MODE_NORMAL_HID  1
#define MODE_ANGLE_TRACK 2
#define MODE_ASSIST      3
#define MODE_ESTOP       4
#define MODE_CALIBRATION 5

// Fault flags
#define FAULT_SERIAL_TIMEOUT  (1 << 0)
#define FAULT_ANGLE_CLAMP     (1 << 1)
#define FAULT_EEPROM_DEFAULTS (1 << 2)
#define FAULT_MOTOR_OVERLOAD  (1 << 3)

WheelConfig cfg;                  // active configuration
uint8_t     wheel_mode     = MODE_IDLE;
float       target_angle   = 0.0f; // degrees
float       current_angle  = 0.0f; // degrees
float       prev_angle     = 0.0f;
float       velocity       = 0.0f; // deg/s
float       prev_velocity  = 0.0f;
float       acceleration   = 0.0f; // deg/s²
float       integral_err   = 0.0f;
float       smoothed_out   = 0.0f;
int         motor_out      = 0;    // -255..+255
uint8_t     fault_flags    = 0;
uint32_t    last_cmd_ms    = 0;
uint32_t    last_telem_ms  = 0;
uint32_t    boot_ms        = 0;
uint32_t    loop_count     = 0;
float       enc_center     = 0.0f; // encoder count at wheel center
char        active_profile_name[PROFILE_NAME_LEN] = "Default";
bool        eeprom_ok      = false;

// Serial command buffer
char cmd_buf[CMD_BUFFER_LEN];
uint8_t cmd_len = 0;

// ═══════════════════════════════════════════════════════════════════
//  ANGLE CALCULATION
// ═══════════════════════════════════════════════════════════════════

float counts_to_degrees(long counts) {
  // counts_per_rev is the encoder counts for one full 360° shaft revolution
  // after accounting for gear ratio
  float effective_cpr = cfg.counts_per_rev * cfg.gear_ratio;
  if (effective_cpr < 1.0f) effective_cpr = 1.0f;
  return ((float)(counts - (long)enc_center) / effective_cpr) * 360.0f;
}

float clamp_angle(float angle) {
  float half = cfg.angle_range * 0.5f;
  if (angle > half)  { fault_flags |= FAULT_ANGLE_CLAMP; return  half; }
  if (angle < -half) { fault_flags |= FAULT_ANGLE_CLAMP; return -half; }
  return angle;
}

// ═══════════════════════════════════════════════════════════════════
//  FFB EFFECTS — applied in NORMAL_HID and ASSIST modes
// ═══════════════════════════════════════════════════════════════════

/*
 * Compute motor output from FFB effects alone (no PD tracking).
 * This simulates the feel of a spring-centered wheel with:
 *   - centering spring:  pulls wheel back to 0°
 *   - damper:            resists angular velocity (like shock absorber)
 *   - friction:          constant resistance opposing any motion
 *   - inertia:           resists angular acceleration
 */
float compute_ffb_output() {
  // 1. Centering spring — proportional to distance from center
  float spring = -cfg.centering * current_angle;

  // 2. Damper — proportional to velocity, opposes motion
  float damp = -cfg.damping * velocity;

  // 3. Friction — constant resistance opposing direction of motion
  float fric = 0.0f;
  if (velocity > 0.5f)       fric = -cfg.friction * (float)cfg.max_motor;
  else if (velocity < -0.5f) fric =  cfg.friction * (float)cfg.max_motor;

  // 4. Inertia — resists changes in velocity
  float iner = -cfg.inertia * acceleration;

  // Combine, scale to max_motor
  float raw = (spring + damp + iner) * (float)cfg.max_motor + fric;

  // Clamp to max_motor
  return constrain(raw, -(float)cfg.max_motor, (float)cfg.max_motor);
}

// ═══════════════════════════════════════════════════════════════════
//  PD CONTROLLER — used in ANGLE_TRACK mode
// ═══════════════════════════════════════════════════════════════════

float compute_pd_output(float dt_s) {
  float error = target_angle - current_angle;

  // Dead zone — ignore tiny errors
  if (fabsf(error) < cfg.dead_zone) {
    integral_err = 0.0f;
    return 0.0f;
  }

  // Integral with anti-windup
  integral_err += error * dt_s;
  float max_integral = 20.0f;
  integral_err = constrain(integral_err, -max_integral, max_integral);

  float raw = (cfg.kp * error)
            - (cfg.kd * velocity)
            + (cfg.ki * integral_err);

  return constrain(raw * (float)cfg.max_motor, -(float)cfg.max_motor, (float)cfg.max_motor);
}

// ═══════════════════════════════════════════════════════════════════
//  SLEW RATE LIMITER
// ═══════════════════════════════════════════════════════════════════

float apply_slew(float target_out, float current_out) {
  if (cfg.slew_rate <= 0.0f) return target_out;
  float delta = target_out - current_out;
  delta = constrain(delta, -cfg.slew_rate, cfg.slew_rate);
  return current_out + delta;
}

// ═══════════════════════════════════════════════════════════════════
//  SERIAL HELPERS
// ═══════════════════════════════════════════════════════════════════

void send_json(JsonDocument &doc) {
  serializeJson(doc, Serial);
  Serial.print('\n');
}

void send_ok(const char *msg = nullptr) {
  StaticJsonDocument<128> doc;
  doc["t"]   = "ok";
  if (msg) doc["msg"] = msg;
  send_json(doc);
}

void send_error(const char *msg) {
  StaticJsonDocument<128> doc;
  doc["t"]   = "error";
  doc["msg"] = msg;
  send_json(doc);
}

const char *mode_name(uint8_t m) {
  switch(m) {
    case MODE_IDLE:        return "IDLE";
    case MODE_NORMAL_HID:  return "NORMAL_HID";
    case MODE_ANGLE_TRACK: return "ANGLE_TRACK";
    case MODE_ASSIST:      return "ASSIST";
    case MODE_ESTOP:       return "ESTOP";
    case MODE_CALIBRATION: return "CALIBRATION";
    default:               return "UNKNOWN";
  }
}

uint8_t parse_mode(const char *s) {
  if (strcmp(s, "IDLE")        == 0) return MODE_IDLE;
  if (strcmp(s, "NORMAL_HID")  == 0) return MODE_NORMAL_HID;
  if (strcmp(s, "ANGLE_TRACK") == 0) return MODE_ANGLE_TRACK;
  if (strcmp(s, "ASSIST")      == 0) return MODE_ASSIST;
  if (strcmp(s, "ESTOP")       == 0) return MODE_ESTOP;
  if (strcmp(s, "CALIBRATION") == 0) return MODE_CALIBRATION;
  return 0xFF; // unknown
}

// ═══════════════════════════════════════════════════════════════════
//  SEND CONFIG — dumps all params as JSON
// ═══════════════════════════════════════════════════════════════════

void send_config() {
  StaticJsonDocument<512> doc;
  doc["t"]             = "config";
  doc["kp"]            = cfg.kp;
  doc["kd"]            = cfg.kd;
  doc["ki"]            = cfg.ki;
  doc["dead_zone"]     = cfg.dead_zone;
  doc["angle_range"]   = cfg.angle_range;
  doc["counts_per_rev"]= cfg.counts_per_rev;
  doc["gear_ratio"]    = cfg.gear_ratio;
  doc["invert_encoder"]= cfg.invert_encoder;
  doc["invert_motor"]  = cfg.invert_motor;
  doc["max_motor"]     = cfg.max_motor;
  doc["slew_rate"]     = cfg.slew_rate;
  doc["centering"]     = cfg.centering;
  doc["damping"]       = cfg.damping;
  doc["friction"]      = cfg.friction;
  doc["inertia"]       = cfg.inertia;
  doc["smoothing"]     = cfg.smoothing;
  doc["profile"]       = active_profile_name;
  doc["eeprom_ok"]     = eeprom_ok;
  send_json(doc);
}

// ═══════════════════════════════════════════════════════════════════
//  SEND PROFILE LIST
// ═══════════════════════════════════════════════════════════════════

void send_profile_list() {
  StaticJsonDocument<512> doc;
  doc["t"] = "profiles";
  JsonArray arr = doc.createNestedArray("slots");
  for (uint8_t i = 0; i < NUM_PROFILES; i++) {
    ProfileSlot ps;
    eeprom_read_profile(i, ps);
    JsonObject o = arr.createNestedObject();
    o["slot"]  = i;
    o["valid"] = (ps.valid == 0xAA);
    if (ps.valid == 0xAA) {
      char safe_name[PROFILE_NAME_LEN + 1];
      memcpy(safe_name, ps.name, PROFILE_NAME_LEN);
      safe_name[PROFILE_NAME_LEN] = '\0';
      o["name"] = safe_name;
    }
  }
  send_json(doc);
}

// ═══════════════════════════════════════════════════════════════════
//  SEND TELEMETRY
// ═══════════════════════════════════════════════════════════════════

void send_telemetry() {
  StaticJsonDocument<384> doc;
  doc["t"]       = "telem";
  doc["angle"]   = (float)(int(current_angle * 10)) / 10.0f;
  doc["target"]  = (float)(int(target_angle  * 10)) / 10.0f;
  doc["motor"]   = motor_out;
  doc["mode"]    = mode_name(wheel_mode);
  doc["enc"]     = enc_count;
  doc["vel"]     = (float)(int(velocity * 10)) / 10.0f;
  doc["fault"]   = fault_flags;
  doc["profile"] = active_profile_name;
  doc["uptime"]  = (millis() - boot_ms) / 1000UL;
  send_json(doc);
}

// ═══════════════════════════════════════════════════════════════════
//  COMMAND HANDLER
// ═══════════════════════════════════════════════════════════════════

void handle_command(const char *json_str) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, json_str);
  if (err) {
    send_error("parse_error");
    return;
  }

  const char *cmd = doc["cmd"] | "";
  last_cmd_ms = millis();

  // ── Ping / version ──────────────────────────────────────────────
  if (strcmp(cmd, "ping") == 0) {
    StaticJsonDocument<64> r;
    r["t"] = "pong";
    send_json(r);
    return;
  }
  if (strcmp(cmd, "get_version") == 0) {
    StaticJsonDocument<128> r;
    r["t"]       = "version";
    r["version"] = FW_VERSION;
    r["target"]  = "Arduino Leonardo";
    send_json(r);
    return;
  }

  // ── ESTOP — highest priority ────────────────────────────────────
  if (strcmp(cmd, "estop") == 0) {
    wheel_mode = MODE_ESTOP;
    motor_stop();
    integral_err = 0.0f;
    send_ok("ESTOP");
    return;
  }

  // ── Clear faults ────────────────────────────────────────────────
  if (strcmp(cmd, "clear_faults") == 0) {
    fault_flags = 0;
    send_ok("faults_cleared");
    return;
  }

  // ── Set mode ────────────────────────────────────────────────────
  if (strcmp(cmd, "set_mode") == 0) {
    const char *m = doc["mode"] | "";
    uint8_t new_mode = parse_mode(m);
    if (new_mode == 0xFF) {
      send_error("unknown_mode");
      return;
    }
    wheel_mode   = new_mode;
    integral_err = 0.0f;
    smoothed_out = 0.0f;
    if (wheel_mode == MODE_IDLE || wheel_mode == MODE_CALIBRATION) {
      motor_stop();
      motor_enable(wheel_mode != MODE_IDLE);
    } else {
      motor_enable(true);
    }
    send_ok(m);
    return;
  }

  // ── Set target angle ────────────────────────────────────────────
  if (strcmp(cmd, "set_target") == 0) {
    float a = doc["angle"] | 0.0f;
    float half = cfg.angle_range * 0.5f;
    target_angle = constrain(a, -half, half);
    send_ok("target_set");
    return;
  }

  // ── Zero encoder ────────────────────────────────────────────────
  if (strcmp(cmd, "zero_encoder") == 0) {
    enc_center = (float)enc_count;
    current_angle = 0.0f;
    target_angle  = 0.0f;
    integral_err  = 0.0f;
    send_ok("encoder_zeroed");
    return;
  }

  // ── Set center (alias for zero_encoder) ─────────────────────────
  if (strcmp(cmd, "set_center") == 0) {
    enc_center = (float)enc_count;
    current_angle = 0.0f;
    send_ok("center_set");
    return;
  }

  // ── Get config ──────────────────────────────────────────────────
  if (strcmp(cmd, "get_config") == 0) {
    send_config();
    return;
  }

  // ── Set one config value ─────────────────────────────────────────
  if (strcmp(cmd, "set_config") == 0) {
    const char *key = doc["key"] | "";
    float fval = doc["value"] | 0.0f;
    bool  bval = doc["value"] | false;

    if      (strcmp(key, "kp")            == 0) cfg.kp            = constrain(fval, 0.0f, 20.0f);
    else if (strcmp(key, "kd")            == 0) cfg.kd            = constrain(fval, 0.0f, 5.0f);
    else if (strcmp(key, "ki")            == 0) cfg.ki            = constrain(fval, 0.0f, 2.0f);
    else if (strcmp(key, "dead_zone")     == 0) cfg.dead_zone     = constrain(fval, 0.0f, 20.0f);
    else if (strcmp(key, "angle_range")   == 0) cfg.angle_range   = constrain(fval, 90.0f, 1080.0f);
    else if (strcmp(key, "counts_per_rev")== 0) cfg.counts_per_rev= constrain(fval, 100.0f, 100000.0f);
    else if (strcmp(key, "gear_ratio")    == 0) cfg.gear_ratio    = constrain(fval, 0.1f, 20.0f);
    else if (strcmp(key, "invert_encoder")== 0) cfg.invert_encoder= (bool)doc["value"];
    else if (strcmp(key, "invert_motor")  == 0) cfg.invert_motor  = (bool)doc["value"];
    else if (strcmp(key, "max_motor")     == 0) cfg.max_motor     = (uint8_t)constrain((int)fval, 0, 255);
    else if (strcmp(key, "slew_rate")     == 0) cfg.slew_rate     = constrain(fval, 0.0f, 255.0f);
    else if (strcmp(key, "centering")     == 0) cfg.centering     = constrain(fval, 0.0f, 5.0f);
    else if (strcmp(key, "damping")       == 0) cfg.damping       = constrain(fval, 0.0f, 2.0f);
    else if (strcmp(key, "friction")      == 0) cfg.friction      = constrain(fval, 0.0f, 1.0f);
    else if (strcmp(key, "inertia")       == 0) cfg.inertia       = constrain(fval, 0.0f, 1.0f);
    else if (strcmp(key, "smoothing")     == 0) cfg.smoothing     = constrain(fval, 0.0f, 0.95f);
    else { send_error("unknown_key"); return; }

    integral_err = 0.0f; // reset integrator on any config change
    send_ok("config_updated");
    return;
  }

  // ── Save active config to EEPROM ────────────────────────────────
  if (strcmp(cmd, "save_config") == 0) {
    eeprom_write_config(cfg);
    eeprom_write_magic();
    send_ok("config_saved");
    return;
  }

  // ── Reload config from EEPROM ───────────────────────────────────
  if (strcmp(cmd, "load_config") == 0) {
    if (eeprom_is_valid()) {
      eeprom_read_config(cfg);
      integral_err = 0.0f;
      send_ok("config_loaded");
    } else {
      send_error("eeprom_invalid");
    }
    return;
  }

  // ── Save profile to a slot ──────────────────────────────────────
  if (strcmp(cmd, "save_profile") == 0) {
    uint8_t slot = doc["slot"] | 0;
    const char *name = doc["name"] | "Profile";
    if (slot >= NUM_PROFILES) { send_error("slot_out_of_range"); return; }
    ProfileSlot ps;
    strncpy(ps.name, name, PROFILE_NAME_LEN - 1);
    ps.name[PROFILE_NAME_LEN - 1] = '\0';
    ps.config = cfg;
    ps.valid  = 0xAA;
    eeprom_write_profile(slot, ps);
    // Also update the active profile name
    strncpy(active_profile_name, name, PROFILE_NAME_LEN - 1);
    active_profile_name[PROFILE_NAME_LEN - 1] = '\0';
    send_ok("profile_saved");
    return;
  }

  // ── Load profile from a slot ────────────────────────────────────
  if (strcmp(cmd, "load_profile") == 0) {
    uint8_t slot = doc["slot"] | 0;
    if (slot >= NUM_PROFILES) { send_error("slot_out_of_range"); return; }
    ProfileSlot ps;
    eeprom_read_profile(slot, ps);
    if (ps.valid != 0xAA) { send_error("slot_empty"); return; }
    cfg = ps.config;
    strncpy(active_profile_name, ps.name, PROFILE_NAME_LEN - 1);
    active_profile_name[PROFILE_NAME_LEN - 1] = '\0';
    integral_err = 0.0f;
    send_ok("profile_loaded");
    return;
  }

  // ── List profiles ───────────────────────────────────────────────
  if (strcmp(cmd, "list_profiles") == 0) {
    send_profile_list();
    return;
  }

  // ── Factory reset ───────────────────────────────────────────────
  if (strcmp(cmd, "factory_reset") == 0) {
    wheel_mode = MODE_IDLE;
    motor_stop();
    eeprom_factory_reset();
    cfg = defaultConfig();
    integral_err = 0.0f;
    smoothed_out = 0.0f;
    target_angle = 0.0f;
    strncpy(active_profile_name, "Default", PROFILE_NAME_LEN - 1);
    send_ok("factory_reset_done");
    return;
  }

  // ── Motor test (raw PWM, diagnostics only) ──────────────────────
  if (strcmp(cmd, "motor_test") == 0) {
    if (wheel_mode != MODE_CALIBRATION) {
      send_error("not_in_calibration_mode");
      return;
    }
    int dir = doc["dir"] | 0;   // +1 or -1
    int pwm = doc["pwm"] | 60;
    pwm = constrain(pwm, 0, (int)cfg.max_motor);
    motor_drive(dir * pwm, cfg.invert_motor);
    delay(300);
    motor_stop();
    send_ok("motor_test_done");
    return;
  }

  send_error("unknown_command");
}

// ═══════════════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════════════

void setup() {
  boot_ms = millis();

  // Pins
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  pinMode(PIN_R_EN,  OUTPUT);
  pinMode(PIN_L_EN,  OUTPUT);
  pinMode(PIN_LED,   OUTPUT);
  motor_enable(false);
  motor_stop();

  // Encoder interrupts
  int8_t a = digitalRead(PIN_ENC_A);
  int8_t b = digitalRead(PIN_ENC_B);
  last_enc_state = (a << 1) | b;
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), enc_isr_a, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), enc_isr_b, CHANGE);

  // Serial
  Serial.begin(SERIAL_BAUD);
  // Brief wait for serial on Leonardo (USB CDC)
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 2000) { }

  // Load config from EEPROM or use defaults
  if (eeprom_is_valid()) {
    eeprom_read_config(cfg);
    eeprom_ok = true;
  } else {
    cfg = defaultConfig();
    fault_flags |= FAULT_EEPROM_DEFAULTS;
    eeprom_ok = false;
  }

  // Boot in IDLE — safe, no motor output
  wheel_mode = MODE_IDLE;
  last_cmd_ms = millis();

  // Announce
  StaticJsonDocument<128> ann;
  ann["t"]       = "boot";
  ann["version"] = FW_VERSION;
  ann["eeprom"]  = eeprom_ok;
  ann["profile"] = active_profile_name;
  send_json(ann);

  // Blink LED to signal ready
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LED, HIGH); delay(80);
    digitalWrite(PIN_LED, LOW);  delay(80);
  }
}

// ═══════════════════════════════════════════════════════════════════
//  MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
  uint32_t now = millis();

  // ── Read serial commands ─────────────────────────────────────────
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_len > 0) {
        cmd_buf[cmd_len] = '\0';
        handle_command(cmd_buf);
        cmd_len = 0;
      }
    } else if (cmd_len < CMD_BUFFER_LEN - 1) {
      cmd_buf[cmd_len++] = c;
    }
  }

  // ── Timing ───────────────────────────────────────────────────────
  static uint32_t last_loop_ms = 0;
  float dt_ms = (float)(now - last_loop_ms);
  if (dt_ms < 1.0f) dt_ms = 1.0f;   // guard against zero
  float dt_s  = dt_ms / 1000.0f;
  last_loop_ms = now;

  // ── Update angle & derivatives ───────────────────────────────────
  long enc_snap;
  noInterrupts();
  enc_snap = enc_count;
  interrupts();

  prev_angle  = current_angle;
  current_angle = counts_to_degrees(enc_snap);
  if (cfg.invert_encoder) current_angle = -current_angle;

  // Velocity (deg/s) — low-pass filtered
  float raw_vel  = (current_angle - prev_angle) / dt_s;
  velocity = velocity * 0.7f + raw_vel * 0.3f;

  // Acceleration (deg/s²)
  acceleration = (velocity - prev_velocity) / dt_s;
  prev_velocity = velocity;

  // ── Serial timeout safety ────────────────────────────────────────
  if ((now - last_cmd_ms) > SERIAL_TIMEOUT_MS &&
      (wheel_mode == MODE_ANGLE_TRACK || wheel_mode == MODE_ASSIST)) {
    wheel_mode = MODE_IDLE;
    motor_stop();
    fault_flags |= FAULT_SERIAL_TIMEOUT;
  }

  // ── Compute motor output by mode ─────────────────────────────────
  float raw_out = 0.0f;

  switch (wheel_mode) {
    case MODE_IDLE:
    case MODE_CALIBRATION:
      motor_stop();
      integral_err = 0.0f;
      smoothed_out = 0.0f;
      break;

    case MODE_ESTOP:
      motor_stop();
      motor_enable(false);
      integral_err = 0.0f;
      smoothed_out = 0.0f;
      break;

    case MODE_ANGLE_TRACK:
      // Clamp target to safe range
      target_angle = clamp_angle(target_angle);
      raw_out = compute_pd_output(dt_s);
      // Apply slew rate and smoothing
      raw_out = apply_slew(raw_out, smoothed_out);
      smoothed_out = smoothed_out * cfg.smoothing + raw_out * (1.0f - cfg.smoothing);
      motor_out = (int)constrain(smoothed_out, -(float)cfg.max_motor, (float)cfg.max_motor);
      motor_drive(motor_out, cfg.invert_motor);
      break;

    case MODE_NORMAL_HID:
    case MODE_ASSIST:
      raw_out = compute_ffb_output();
      raw_out = apply_slew(raw_out, smoothed_out);
      smoothed_out = smoothed_out * cfg.smoothing + raw_out * (1.0f - cfg.smoothing);
      motor_out = (int)constrain(smoothed_out, -(float)cfg.max_motor, (float)cfg.max_motor);
      motor_drive(motor_out, cfg.invert_motor);
      break;
  }

  // ── LED heartbeat ────────────────────────────────────────────────
  digitalWrite(PIN_LED, ((now / 500) % 2 == 0) ? HIGH : LOW);

  // ── Send telemetry ───────────────────────────────────────────────
  if ((now - last_telem_ms) >= TELEM_RATE_MS) {
    send_telemetry();
    last_telem_ms = now;
  }

  loop_count++;
}
