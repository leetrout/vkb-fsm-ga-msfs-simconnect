from enum import IntEnum, Enum, auto
import sys
import time

from vkb import led, devices
from SimConnect import SimConnect, AircraftRequests

FSM_GA_PID = 0x2220


class FSMGALED(IntEnum):
    """LED IDs starting from the HDG button.
    My device starts at 10. Unsure how this changes from device
    to device. Can add an offset start later if needed.
    """

    HDG = 10
    TRK = auto()
    NAV = auto()
    APR = auto()
    ALT = auto()
    LVL = auto()
    VNAV = auto()
    IAS = auto()
    AP = auto()
    FD = auto()
    YD = auto()
    VS = auto()


LOOKUP_LED_BY_ID = {int(x.value): x.name for x in FSMGALED}


class FSMGADevice(devices.base.VKBDevice):
    """Our FSM GA device compatible with the vkb lib."""

    # NB: Required from base class
    PRODUCT_ID = FSM_GA_PID

    # Helper for looping over all the LED IDs
    ALL_LEDS = list(range(FSMGALED.HDG, FSMGALED.HDG + len(FSMGALED)))

    def set_led_on(self, led_id):
        """Turns the LED 'on' by setting it to green."""
        self.set_led(
            led_id,
            "#0f0",
            color_mode=led.ColorMode.COLOR1,
            led_mode=led.LEDMode.CONSTANT,
        )

    def set_led_flashing(self, led_id):
        """Sets to yellowish flashing."""
        self.set_led(
            led_id,
            "#030",
            color_mode=led.ColorMode.COLOR1_p_2,
            led_mode=led.LEDMode.SLOW_BLINK,
            color2="#f00",
        )

    def set_led_off(self, led_id):
        """Turns the LED 'off' by setting it to black so it is not illuminated."""
        self.set_led(
            led_id,
            "#000",
            color_mode=led.ColorMode.COLOR1,
            led_mode=led.LEDMode.CONSTANT,
        )

    def flash_led(self, led_id):
        self.set_led(
            led_id,
            "#f00",
            color_mode=led.ColorMode.COLOR1,
            led_mode=led.LEDMode.FAST_BLINK,
        )

    def all_leds_off(self):
        for led_id in LOOKUP_LED_BY_ID:
            self.set_led(led_id, "#000")
            time.sleep(0.05)


# Monkey patch the FSM device into the device lookup map
devices.VKB_DEVICES[FSM_GA_PID] = FSMGADevice


def get_fsmga(device_list):
    filtered_devices = [x for x in device_list if x.PRODUCT_ID == FSM_GA_PID]
    if len(filtered_devices) > 1:
        raise RuntimeError("Multiple devices is not supported")

    if not filtered_devices:
        raise RuntimeError(f"Could not find FSM GA device in {device_list}")

    return filtered_devices[0]


#
# Sim Sync
#
# See
# Autopilot https://docs.flightsimulator.com/html/Programming_Tools/SimVars/Aircraft_SimVars/Aircraft_AutopilotAssistant_Variables.htm
class AIRCRAFT_SYSTEM(str, Enum):
    AP_HEADING_LOCK = "AUTOPILOT_HEADING_LOCK"

    AP_ALT_ARM = "AUTOPILOT_ALTITUDE_ARM"
    AP_ALT_LOCK = "AUTOPILOT_ALTITUDE_LOCK"

    AP_WING_LEVELER = "AUTOPILOT_WING_LEVELER"
    AP_YD = "AUTOPILOT_YAW_DAMPER"


# Cache the known state so we avoid unnecessary LED changes.
KNOWN_LED_STATE = {}


def _set_bool_led(led_id: int, sim_attr: str, fsmga: FSMGADevice, aircraft_state):
    """Helper for setting simple LEDs based on boolean properties."""
    known_state = KNOWN_LED_STATE.get(led_id)
    sim_state = aircraft_state.get(sim_attr) or 0

    if sim_state > 0 and not known_state:
        fsmga.set_led_on(led_id)
        KNOWN_LED_STATE[led_id] = 1
        return

    if not sim_state and known_state:
        fsmga.set_led_off(led_id)
        KNOWN_LED_STATE[led_id] = 0


def led_update_noop(led_id: int, fsmga: FSMGADevice, aircraft_state):
    """Placeholder."""
    pass


# Left side buttons


def led_update_hdg(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_HEADING_LOCK", fsmga, aircraft_state)


def led_update_nav(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_NAV1_LOCK", fsmga, aircraft_state)


def led_update_apr(led_id: int, fsmga: FSMGADevice, aircraft_state):
    known_state = KNOWN_LED_STATE.get(led_id)

    apr_armed = (aircraft_state.get("AUTOPILOT_APPROACH_ARM") or 0) > 0
    apr_active = (aircraft_state.get("AUTOPILOT_APPROACH_ACTIVE") or 0) > 0
    apr_captured = (aircraft_state.get("AUTOPILOT_APPROACH_CAPTURED") or 0) > 0
    apr_hold = (aircraft_state.get("AUTOPILOT_APPROACH_HOLD") or 0) > 0

    gs_armed = (aircraft_state.get("AUTOPILOT_GLIDESLOPE_ARM") or 0) > 0
    gs_active = (aircraft_state.get("AUTOPILOT_GLIDESLOPE_ACTIVE") or 0) > 0

    # Should the LED be lit?
    if (apr_active or apr_captured or gs_active or apr_hold) and known_state != "on":
        fsmga.set_led_on(led_id)
        KNOWN_LED_STATE[led_id] = "on"
        return

    # Should the LED be flashing?
    if (apr_armed or gs_armed) and known_state != "flash":
        fsmga.set_led_flashing(led_id)
        KNOWN_LED_STATE[led_id] = "flash"
        return

    # Turn off the LED
    if (
        not any([apr_armed, apr_active, apr_captured, apr_hold, gs_active, gs_armed])
        and known_state != "off"
    ):
        fsmga.set_led_off(led_id)
        KNOWN_LED_STATE[led_id] = "off"


# Right side buttons


def led_update_alt(led_id: int, fsmga: FSMGADevice, aircraft_state):
    known_state = KNOWN_LED_STATE.get(led_id, "off") or "off"

    armed = (aircraft_state.get("AUTOPILOT_ALTITUDE_ARM") or 0) > 0
    locked = (aircraft_state.get("AUTOPILOT_ALTITUDE_LOCK") or 0) > 0

    if locked and known_state != "locked":
        fsmga.set_led_on(led_id)
        KNOWN_LED_STATE[led_id] = "locked"
        return

    if armed and known_state != "armed":
        fsmga.set_led_flashing(led_id)
        KNOWN_LED_STATE[led_id] = "armed"
        return

    if not locked and not armed and known_state != "off":
        fsmga.set_led_off(led_id)
        KNOWN_LED_STATE[led_id] = "off"


def led_update_lvl(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_WING_LEVELER", fsmga, aircraft_state)


def led_update_vnav(led_id: int, fsmga: FSMGADevice, aircraft_state):
    """FIXME: There should be something we can determine the vnav mode from."""
    pass


def led_update_ias_as_flc(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_FLIGHT_LEVEL_CHANGE", fsmga, aircraft_state)


# Center buttons


def led_update_ap(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_MASTER", fsmga, aircraft_state)


def led_update_fd(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_FLIGHT_DIRECTOR_ACTIVE", fsmga, aircraft_state)


def led_update_yd(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_YAW_DAMPER", fsmga, aircraft_state)


def led_update_vs(led_id: int, fsmga: FSMGADevice, aircraft_state):
    _set_bool_led(led_id, "AUTOPILOT_VERTICAL_HOLD", fsmga, aircraft_state)


def led_update_loop(fsmga: FSMGADevice, aircraft_state: AircraftRequests):
    LED_UPDATER_MAP = {
        FSMGALED.HDG: led_update_hdg,
        FSMGALED.TRK: led_update_noop,  # Unused, TBD
        FSMGALED.NAV: led_update_nav,
        FSMGALED.APR: led_update_apr,
        FSMGALED.ALT: led_update_alt,
        FSMGALED.LVL: led_update_lvl,
        FSMGALED.VNAV: led_update_noop,  # Missing simconnect, maybe use mobiflight?
        FSMGALED.IAS: led_update_ias_as_flc,
        FSMGALED.AP: led_update_ap,
        FSMGALED.FD: led_update_fd,
        FSMGALED.YD: led_update_yd,
        FSMGALED.VS: led_update_vs,
    }

    for led_id, update_func in LED_UPDATER_MAP.items():
        update_func(int(led_id), fsmga, aircraft_state)


def run_simconnect():
    print("Finding FSM GA device")
    fsmga = get_fsmga(devices.find_all_vkb())

    print("Turning off LEDs")
    fsmga.all_leds_off()

    # Mark all LEDs and known to be off
    for led_id in LOOKUP_LED_BY_ID:
        KNOWN_LED_STATE[led_id] = 0

    print("Starting SimConnect")
    sim = SimConnect()
    aircraft_state = AircraftRequests(sim)

    print("Running...")
    while not sim.quit:
        led_update_loop(fsmga, aircraft_state)
        time.sleep(0.25)


#
# Self Test
#


def perform_self_test():
    print("Performing LED self test")

    fsmga = get_fsmga(devices.find_all_vkb())
    print(f"FSM-GA device found: {fsmga.name} ({fsmga.guid})")

    print("Turning off all LEDs")
    fsmga.all_leds_off()

    for led_id, led_name in sorted(LOOKUP_LED_BY_ID.items(), key=lambda x: x[0]):
        print(f"Flashing {led_name}")
        fsmga.flash_led(led_id)
        time.sleep(2)
        fsmga.set_led_off(led_id)
        time.sleep(0.2)


#
# Init
#


def main():
    match sys.argv[1:]:
        case ["test"]:
            perform_self_test()
        case _:
            run_simconnect()


if __name__ == "__main__":
    main()
