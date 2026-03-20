"""
pid_speed_controller.py - PID-based longitudinal speed controller.

Converts a target speed (kph) and current speed (kph) into throttle and
brake commands.
"""

import math


class PIDSpeedController:
    """
    Longitudinal speed controller.

    Features:
    - PID on speed error
    - Coast band (dead zone around target)
    - Separate throttle and brake channels
    - Rate limiting on actuator changes
    - Steering-based throttle reduction (trail braking)
    """

    def __init__(self, config=None):
        # PID gains
        self.kp: float = 0.14
        self.ki: float = 0.010
        self.kd: float = 0.04

        # Brake gains
        self.brake_kp: float = 0.12
        self.brake_extra_gain: float = 0.18
        self.strong_brake_delta_kph: float = 10.0

        # Output limits
        self.throttle_max: float = 0.86
        self.brake_max: float = 1.0
        self.coast_band_kph: float = 3.0

        # Rate limits (per tick, assuming ~25 Hz)
        self.throttle_rate_up: float = 0.12
        self.throttle_rate_down: float = 0.30
        self.brake_rate_up: float = 0.28
        self.brake_rate_down: float = 0.30

        # Trail braking
        self.steering_throttle_reduction: float = 0.58
        self.trail_brake_steer: float = 0.30
        self.straight_brake_steer: float = 0.05

        if config is not None:
            self._load_config(config)

        # State
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_throttle: float = 0.0
        self._prev_brake: float = 0.0
        self._integral_max: float = 5.0  # anti-windup

    def _load_config(self, config) -> None:
        try:
            pid = config.controllers.speed_pid
            self.kp = float(pid.kp)
            self.ki = float(pid.ki)
            self.kd = float(pid.kd)
            self.brake_kp = float(pid.brake_kp)
            self.brake_extra_gain = float(pid.brake_extra_gain)
            self.strong_brake_delta_kph = float(pid.strong_brake_delta_kph)
            self.throttle_max = float(pid.throttle_max)
            self.brake_max = float(pid.brake_max)
            self.coast_band_kph = float(pid.coast_band_kph)
            self.throttle_rate_up = float(pid.throttle_rate_up)
            self.throttle_rate_down = float(pid.throttle_rate_down)
            self.brake_rate_up = float(pid.brake_rate_up)
            self.brake_rate_down = float(pid.brake_rate_down)
            self.steering_throttle_reduction = float(pid.steering_throttle_reduction)
            self.trail_brake_steer = float(pid.trail_brake_steer)
            self.straight_brake_steer = float(pid.straight_brake_steer)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        target_kph: float,
        current_kph: float,
        steering: float = 0.0,
        dt: float = 0.04,
    ) -> tuple:
        """
        Compute throttle and brake commands.

        Parameters
        ----------
        target_kph  : desired speed in kph
        current_kph : current speed in kph
        steering    : current steering input [-1, 1]
        dt          : time step in seconds

        Returns
        -------
        (throttle, brake) both in [0, 1]
        """
        error_kph = target_kph - current_kph

        # Coast band - do nothing near target
        if abs(error_kph) < self.coast_band_kph:
            throttle = 0.0
            brake = 0.0
            # Decay integral gently
            self._integral *= 0.95
            self._prev_error = error_kph
            throttle = self._rate_limit(throttle, self._prev_throttle,
                                        self.throttle_rate_down, self.throttle_rate_down)
            brake = self._rate_limit(brake, self._prev_brake,
                                     self.brake_rate_down, self.brake_rate_down)
            self._prev_throttle = throttle
            self._prev_brake = brake
            return throttle, brake

        # PID terms
        self._integral += error_kph * dt
        self._integral = max(-self._integral_max, min(self._integral_max, self._integral))
        derivative = (error_kph - self._prev_error) / max(dt, 1e-4)
        self._prev_error = error_kph

        pid_output = self.kp * error_kph + self.ki * self._integral + self.kd * derivative

        if error_kph > 0:
            # Accelerate
            throttle_raw = max(0.0, pid_output)

            # Steering-based throttle reduction (trail braking approach)
            steer_abs = abs(steering)
            if steer_abs > self.trail_brake_steer:
                reduction = self.steering_throttle_reduction * min(
                    1.0, (steer_abs - self.trail_brake_steer)
                         / max(1.0 - self.trail_brake_steer, 1e-3)
                )
                throttle_raw *= (1.0 - reduction)

            throttle_raw = min(throttle_raw, self.throttle_max)
            throttle = self._rate_limit(throttle_raw, self._prev_throttle,
                                        self.throttle_rate_up, self.throttle_rate_down)
            brake = self._rate_limit(0.0, self._prev_brake,
                                     self.brake_rate_down, self.brake_rate_down)
        else:
            # Decelerate
            throttle = self._rate_limit(0.0, self._prev_throttle,
                                        self.throttle_rate_down, self.throttle_rate_down)
            # Brake proportional to speed excess
            excess = abs(error_kph)
            brake_raw = self.brake_kp * excess
            if excess > self.strong_brake_delta_kph:
                brake_raw += self.brake_extra_gain * (excess - self.strong_brake_delta_kph)
            brake_raw = min(brake_raw, self.brake_max)
            brake = self._rate_limit(brake_raw, self._prev_brake,
                                     self.brake_rate_up, self.brake_rate_down)

        throttle = max(0.0, min(self.throttle_max, throttle))
        brake = max(0.0, min(self.brake_max, brake))

        self._prev_throttle = throttle
        self._prev_brake = brake

        return throttle, brake

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_throttle = 0.0
        self._prev_brake = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rate_limit(target: float, current: float, rate_up: float, rate_down: float) -> float:
        delta = target - current
        if delta > 0:
            delta = min(delta, rate_up)
        else:
            delta = max(delta, -rate_down)
        return current + delta
