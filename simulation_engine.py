
from datetime import datetime, timedelta
import time



class SimulationClock:


    def __init__(self, mode="real_time", start_time=None):

        if mode not in ("real_time", "accelerated"):
            raise ValueError(
                "Mode must be 'real_time' or 'accelerated'."
            )

        self.mode = mode
        self.speed = 5

        # Starting point for accelerated simulation.
        self.start_time = start_time or datetime.now()

        # Real elapsed time is measured using a monotonic clock.
        self._real_start = time.monotonic()

        self._elapsed_before_pause = 0
        self._paused = False

    def get_current_time(self):

        # Mode 1: Follow the actual computer clock.
        if self.mode == "real_time":
            return datetime.now()

        # Mode 2: Advance simulation time at 5x speed.
        if self._paused:
            elapsed_seconds = self._elapsed_before_pause
        else:
            elapsed_seconds = (
                self._elapsed_before_pause
                + time.monotonic()
                - self._real_start
            )

        simulated_seconds = elapsed_seconds * self.speed

        return self.start_time + timedelta(
            seconds=simulated_seconds
        )

    def pause(self):

        if self.mode == "real_time":
            raise ValueError(
                "Real-time mode cannot be paused."
            )

        if not self._paused:
            self._elapsed_before_pause += (
                time.monotonic() - self._real_start
            )

            self._paused = True

    def resume(self):

        if self.mode == "real_time":
            raise ValueError(
                "Real-time mode does not need resuming."
            )

        if self._paused:
            self._real_start = time.monotonic()
            self._paused = False

    def restart(self):

        if self.mode == "real_time":
            raise ValueError(
                "Real-time mode follows the computer clock."
            )

        self._real_start = time.monotonic()
        self._elapsed_before_pause = 0
        self._paused = False

    def get_status(self):

        return {
            "mode": self.mode,
            "speed": self.speed if self.mode == "accelerated" else 1,
            "current_time": self.get_current_time().strftime(
                "%d-%m-%Y %H:%M:%S"
            ),
            "paused": self._paused
        }
if __name__ == "__main__":

    print("\nREAL-TIME CLOCK TEST")

    real_clock = SimulationClock(mode="real_time")
    print(real_clock.get_status())

    print("\nACCELERATED CLOCK TEST")

    journey_start = datetime.now()

    fast_clock = SimulationClock(
        mode="accelerated",
        start_time=journey_start
    )

    print("Starting:", fast_clock.get_current_time())

    time.sleep(5)

    print("After 5 real seconds:", fast_clock.get_current_time())

    print("\nPAUSE TEST")

    fast_clock.pause()

    paused_time = fast_clock.get_current_time()
    time.sleep(2)

    print("Before:", paused_time)
    print("After:", fast_clock.get_current_time())

    print("\nRESUME TEST")

    fast_clock.resume()
    time.sleep(2)

    print("After resuming:", fast_clock.get_current_time())

    print("\nRESTART TEST")

    fast_clock.restart()
    print("Restarted:", fast_clock.get_current_time())