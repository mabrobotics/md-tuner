import time
import threading
import pyCandle as pc


class DriveBackend:

    def __init__(self, md):
        self.md = md
        self.running = False
        self.abort_flag = False

    # =========================
    # SAFE CONVERT
    # =========================
    def _to_float(self, x):
        if isinstance(x, (tuple, list)):
            x = x[0]
        return float(str(x).replace(",", "."))
    
    def get_temperature(self):
        try:
            temp = self.md.getTemperature()

            # FIX: tuple → float
            if isinstance(temp, (tuple, list)):
                temp = temp[0]

            return float(temp)

        except Exception as e:
            print("Temperature read error:", e)
            return None
    def get_position(self):
        try:
            pos = self.md.getPosition()

            if isinstance(pos, (tuple, list)):
                pos = pos[0]

            return float(pos)

        except:
            return None
        

    # =========================
    # CONFIG
    # =========================
    def configure(self, mode, kp, ki, kd):
        self.mode = mode
        self.kp = kp
        self.ki = ki
        self.kd = kd

        if mode == "Position":
            self.md.setMotionMode(pc.MotionMode_t.POSITION_PID)
        else:
            self.md.setMotionMode(pc.MotionMode_t.VELOCITY_PID)

    # =========================
    # START TEST
    # =========================
    def start_test(self, mode, target, duration, callback=None):

        if self.running:
            return

        self.running = True
        self.abort_flag = False

        target = self._to_float(target)
        duration = self._to_float(duration)

        threading.Thread(
            target=self._loop,
            args=(mode, target, duration, callback),
            daemon=True
        ).start()

    # =========================
    # STOP
    # =========================
    def stop(self):
        self.abort_flag = True
        self.running = False

        try:
            self.md.setTargetPosition(0.0)
            self.md.setTargetVelocity(0.0)
            self.md.disable()
        except Exception as e:
            print("STOP ERROR:", e)

    # =========================
    # MAIN LOOP
    # =========================
    def _loop(self, mode, target, duration, callback):

        try:
            self.md.zero()

            if mode == "Position":
                self.md.setMotionMode(pc.MotionMode_t.POSITION_PID)
            else:
                self.md.setMotionMode(pc.MotionMode_t.VELOCITY_PID)

            time.sleep(0.05)

            self.md.enable()
            time.sleep(0.05)

            start = time.time()

            while True:

                if self.abort_flag:
                    break

                t = time.time() - start
                if t >= duration:
                    break

                if mode == "Position":
                    self.md.setTargetPosition(target)
                    actual = self._to_float(self.md.getPosition())
                else:
                    self.md.setTargetVelocity(target)
                    actual = self._to_float(self.md.getVelocity())

                if callback:
                    callback({
                        "time": float(t),
                        "actual": float(actual),
                        "target": float(target),
                        "mode": mode,
                        "error": float(target - actual)
                    })

                time.sleep(0.005)

            self.md.disable()

            if callback:
                callback({"event": "finished"})

        except Exception as e:
            if callback:
                callback({"event": "error", "msg": str(e)})

        self.running = False