"""
GPS Hexpansion firmware (minimal) for the Tildagon badge.

Kept deliberately small to fit the tiny (2 KB) M24C16 EEPROM: it parses RMC for
position/speed/bearing (and emits the unchanged GPSEvent, so the emf-speedometer
app keeps working), and buffers the recent raw NMEA sentences so apps can parse
whatever else they need (GGA/GSV/GSA for altitude, satellite counts, sky maps)
themselves, on the badge where there is plenty of space.

checks for unused UART resource before using either UART1 or UART2

Based on the GPS firmware from https://github.com/mbooth101/emf-speedometer
License: MIT
"""
import app
import asyncio
import time

from events import Event
from system.eventbus import eventbus
from machine import UART, Pin, mem32
from micropython import const

# --- Pre-evaluated ESP32-S3 Hardware Registers & Masks ---
_CLK_REG   = const(0x600C0018)  # SYSTEM_PERIP_CLK_EN0_REG
_U1_BIT    = const(1 << 5)      # UART1 clock enable bit
_U2_BIT    = const(1 << 23)     # UART2 clock enable bit

class GPSApp(app.App):
    """Provides a GPS API for apps to use directly and GPS Events to subscribe to."""

    # Increment when the firmware changes in a way that needs a re-flash.
    VERSION = 1

    class GPSEvent(Event):
        def __init__(self, position, speed, bearing):
            self.position = position
            self.speed = speed
            self.bearing = bearing

        def __str__(self):
            return f"GPS fix {self.position}, speed {self.speed} knots, bearing {self.bearing}"

    def __init__(self, config=None):
        super().__init__()
        if config is None:
            raise TypeError
        self.config = config

        self._position = None
        self._bearing = 0
        self._speed = 0

        # Ring buffer of recent raw NMEA sentences (checksum stripped)
        self._lines = []

        self.to = 10
        self.uart = None
        u = 0

        # try to initialise UART 1 or 2 for GPS use
        # micropython is rather flawed and assumes that there is one 'thing' controlling use of the hardware
        # which it expects to manage which UARTs are used for what, hence if we ask for UART1 we get it regardless
        # of wheter it was already allocated to something else.  Unfortunately the hexpansion system
        # allows for many different hardware configurations so we can't always have UART1 (or even UART2)
        # Check if UART peripheral clock gating is enabled
        if not (mem32[_CLK_REG] & _U1_BIT):
            # no - so UART1 is available
            u = 1
        elif not (mem32[_CLK_REG] & _U2_BIT):
            # no - so UART2 is available
            u = 2
        if 0 < u:
            self.uart = UART(u, baudrate=9600, tx=config.pin[0], rx=config.pin[1], timeout=self.to)

        self.r = config.pin[2]
        self.r.init(mode=Pin.OUT)
        self.r.value(1)

        self.z = 0

    # Special function called by the BadgeOS to allow the app to clean up resources before it is removed from memory.
    # See https://github.com/emfcamp/badge-2024-software/pull/328
    def deinit(self):
        """release the UART."""
        if self.uart is not None:
            self.uart.deinit()

    @property
    def position(self):
        return self._position

    @property
    def bearing(self):
        return self._bearing

    @property
    def speed(self):
        return self._speed # round(self._speed, 2) - leave rounding to receiving app to save code space

    @property
    def sentences(self):
        """Recent raw NMEA sentences (checksum stripped) for apps to parse."""
        return list(self._lines)

    async def background_task(self):
        last = time.ticks_ms()
        while True:
            start = time.ticks_ms()
            delta = time.ticks_diff(start, last)
            result = self.background_update(delta)
            await asyncio.sleep_ms(25 if result else 250 - self.to)
            last = start

    def background_update(self, delta):
        self.z += delta

        if self.r.value():
            if self.z > 99:
                self.r.value(0)

        if self._position and self.z > 9999:
            self._position = None
            self._speed = 0
        try:
            l = self.uart.readline()        # moved inside try block as the least code to cope with potential that we don't actually have a uart
            if not l:
                return False
            line = l.decode().strip().split('*')[0]
            self._lines.append(line)
            if len(self._lines) > 40:
                self._lines = self._lines[-40:]

            p = line.split(',')
            if p[0][3:] == "RMC":
                if p[2] == "A":
                    lat = float(p[3][:2]) + float(p[3][2:]) / 60
                    lon = float(p[5][:3]) + float(p[5][3:]) / 60
                    if p[4] == "S":
                        lat = -lat
                    if p[6] == "W":
                        lon = -lon
                    self._position = (round(lat, 5), round(lon, 5))
                    self._speed = float(p[7]) if p[7] else 0.0
                    if p[8]:
                        self._bearing = float(p[8])
                    # Ignoring small speeds can be done in the application to save code space
                    # #if self._speed < 1:
                    #    self._speed = 0
                    self.z = 0
                eventbus.emit(self.GPSEvent(self._position, self._speed, self._bearing))
        except: # removed to save code space (UnicodeError, ValueError, AttributeError, IndexError):
            pass
        return True

__app_export__ = GPSApp # pylint: disable=invalid-name
