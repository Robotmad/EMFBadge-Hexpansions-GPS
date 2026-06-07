import app

from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from system.hexpansion.util import get_app_by_vid_pid


class GPS(app.App):

    def __init__(self):
        self.gps = get_app_by_vid_pid(0x7CAB, 0xBEAC)

        self.last_position = None
        self.last_speed = 0
        self.last_bearing = 0

        if self.gps:
            eventbus.on(
                self.gps.GPSEvent,
                self.handle_gps_event,
                self
            )
            print("GPS Hexpansion found")
        else:
            print("GPS Hexpansion NOT found")

        self.button_states = Buttons(self)
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        eventbus.on(ButtonUpEvent, self._handle_buttonup, self)

    def on_resume(self):
        print("resumed")
    
    def on_pause(self):
        print("paused")

    def _handle_buttondown(self, event: ButtonDownEvent):
        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left Button Down")
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right Button Down")
            self.button_states.clear()

        if BUTTON_TYPES["DOWN"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["CANCEL"] in event.button:
            self.button_states.clear()
            self.minimise()
    
    def _handle_buttonup(self, event: ButtonUpEvent):
        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left Button Up")
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right Button Up")
            self.button_states.clear()

    def handle_gps_event(self, event):

        self.last_position = event.position
        self.last_speed = event.speed
        self.last_bearing = event.bearing

        print("GPS Event")
        print("Position:", event.position)
        print("Speed:", event.speed)
        print("Bearing:", event.bearing)

    def update(self, delta):
        pass

    def draw(self, ctx):

        ctx.rgb(0, 0.2, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(0, 1, 0)

        if not self.gps:
            ctx.move_to(-100, 0).text("GPS Not Found")
            return

        if not self.last_position:
            ctx.move_to(-100, 0).text("Waiting For Fix")
            return

        lat, lon = self.last_position

        ctx.move_to(-110, -40).text(
            "Lat: %.5f" % lat
        )

        ctx.move_to(-110, -10).text(
            "Lon: %.5f" % lon
        )

        ctx.move_to(-110, 20).text(
            "Spd: %.1f kt" % self.last_speed
        )

        ctx.move_to(-110, 50).text(
            "Brg: %.0f" % self.last_bearing
        )


__app_export__ = GPS