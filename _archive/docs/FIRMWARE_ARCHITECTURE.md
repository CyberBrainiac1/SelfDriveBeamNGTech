# Firmware Architecture — wheel_controller.ino v2.0.0

## Target: Arduino Leonardo (ATmega32U4)

---

## EEPROM Layout

```
Addr 0x000 │ uint32_t magic       (0xABCD1234 = valid)
Addr 0x004 │ WheelConfig          active config (~56 bytes)
Addr 0x040 │ ProfileSlot[4]       named presets (~76 bytes × 4)
─────────────────────────────────────────────────────────
Total used: ~352 / 1024 bytes
```

On boot the firmware reads the magic number. If valid it loads `WheelConfig`
from EEPROM and sets `eeprom_ok = true`. If invalid (blank board or after
factory reset) it loads safe defaults and raises `FAULT_EEPROM_DEFAULTS`.

---

## WheelConfig Fields

| Field            | Default | Range         | Description                           |
|------------------|---------|---------------|---------------------------------------|
| `kp`             | 1.8     | 0 – 20        | PD proportional gain                  |
| `kd`             | 0.12    | 0 – 5         | PD derivative gain                    |
| `ki`             | 0.0     | 0 – 2         | PD integral gain (use sparingly)      |
| `dead_zone`      | 1.5°    | 0 – 20°       | Error band with no output             |
| `angle_range`    | 540°    | 90 – 1080°    | Total rotation range                  |
| `counts_per_rev` | 2400    | 100 – 100000  | Encoder CPR (×4 quadrature)           |
| `gear_ratio`     | 1.0     | 0.1 – 20      | Motor-to-shaft ratio                  |
| `invert_encoder` | false   | bool          | Flip encoder direction                |
| `invert_motor`   | false   | bool          | Flip motor direction                  |
| `max_motor`      | 200     | 0 – 255       | Absolute PWM ceiling                  |
| `slew_rate`      | 20      | 0 – 255       | Max PWM change per loop (0 = off)     |
| `centering`      | 1.0     | 0 – 5         | Spring-center strength                |
| `damping`        | 0.12    | 0 – 2         | Velocity-proportional resistance      |
| `friction`       | 0.05    | 0 – 1         | Constant rotational resistance        |
| `inertia`        | 0.04    | 0 – 1         | Acceleration-proportional resistance  |
| `smoothing`      | 0.10    | 0 – 0.95      | LP filter on motor output             |

---

## Modes

| Mode          | Encoder | Motor Output | Description                             |
|---------------|---------|-------------|-----------------------------------------|
| `IDLE`        | ✓       | Off         | Safe default on boot                    |
| `NORMAL_HID`  | ✓       | FFB effects | Spring + damper + friction + inertia    |
| `ANGLE_TRACK` | ✓       | PD control  | Follow target_angle                     |
| `ASSIST`      | ✓       | FFB effects | Same as NORMAL_HID (for shared-control) |
| `CALIBRATION` | ✓       | Manual test | motor_test command only                 |
| `ESTOP`       | —       | Off + disable driver | Latched until set_mode command  |

---

## FFB Effects (NORMAL_HID / ASSIST)

```
spring   = -centering × current_angle
damper   = -damping   × velocity
friction = -sign(velocity) × friction × max_motor   [if |vel| > 0.5 °/s]
inertia  = -inertia   × acceleration
raw_out  = (spring + damper + inertia) × max_motor + friction
smoothed = smoothed × smoothing + raw_out × (1 − smoothing)
```

---

## PD Controller (ANGLE_TRACK)

```
error    = target_angle − current_angle
integral += error × dt                    [with ±20° anti-windup]
raw_out  = kp×error − kd×velocity + ki×integral   [scaled by max_motor]
```

If `|error| < dead_zone` → output = 0, integrator reset.

---

## Serial Protocol

All messages: single-line JSON + `\n`, 115200 baud.

### Commands (PC → Arduino)

| Command             | Key params                         | Description              |
|---------------------|------------------------------------|--------------------------|
| `ping`              | —                                  | Returns `{"t":"pong"}`   |
| `get_version`       | —                                  | Returns version string   |
| `set_mode`          | `mode`                             | Switch operating mode    |
| `set_target`        | `angle`                            | Set target angle (°)     |
| `set_config`        | `key`, `value`                     | Set one config param     |
| `get_config`        | —                                  | Dump full config         |
| `save_config`       | —                                  | **Write config to EEPROM**|
| `load_config`       | —                                  | **Reload from EEPROM**   |
| `save_profile`      | `slot` (0–3), `name`               | **Save named profile**   |
| `load_profile`      | `slot` (0–3)                       | **Load named profile**   |
| `list_profiles`     | —                                  | **List all slot names**  |
| `factory_reset`     | —                                  | **Erase EEPROM + defaults**|
| `zero_encoder`      | —                                  | Set encoder zero here    |
| `set_center`        | —                                  | Set wheel center here    |
| `motor_test`        | `dir` (+1/−1), `pwm`               | Test pulse (CAL mode)    |
| `clear_faults`      | —                                  | Clear fault flags        |
| `estop`             | —                                  | Immediate motor cutoff   |

### Telemetry (Arduino → PC, ~50 Hz)

```json
{"t":"telem","angle":42.3,"target":45.0,"motor":120,
 "mode":"ANGLE_TRACK","enc":1234,"vel":18.5,
 "fault":0,"profile":"Normal","uptime":60}
```

### Fault Flags

| Bit | Value | Meaning                        |
|-----|-------|-------------------------------|
| 0   | 0x01  | Serial timeout (motor killed) |
| 1   | 0x02  | Angle clamped to range limit  |
| 2   | 0x04  | EEPROM invalid (using defaults)|
| 3   | 0x08  | Motor overload (future use)   |

---

## Safety

- Motor disabled at boot (`motor_enable(false)`)
- Serial timeout: motor off if no command for 500 ms in ANGLE_TRACK/ASSIST
- Max PWM clamp enforced in every code path
- ESTOP disables motor driver (R_EN + L_EN = LOW)
- ESTOP only cleared by explicit `set_mode` command
- Software angle clamp sets `FAULT_ANGLE_CLAMP` flag

---

## Pin Assignments

| Signal       | Pin  |
|--------------|------|
| Encoder A    | 2 (INT0) |
| Encoder B    | 3 (INT1) |
| BTS7960 RPWM | 9 (PWM)  |
| BTS7960 LPWM | 10 (PWM) |
| BTS7960 R_EN | 7        |
| BTS7960 L_EN | 8        |
| Status LED   | 13       |

---

## Building the Hex

```powershell
.\build_hex.ps1
# Output: .\output\firmware\wheel_controller.hex

.\flash_hex.ps1   # optional — auto-flash to connected Leonardo
```
