#
# Thermostat.py - Jordan Bankston
#
# Purpose:
# A simple thermostat prototype with three modes (OFF / HEAT / COOL).
# - LCD line 1: date/time
# - LCD line 2: alternates between current temp and (state + setpoint)
# - LEDs:
#     OFF  -> both off
#     HEAT -> red pulses when temp < setpoint, else solid red
#     COOL -> blue pulses when temp > setpoint, else solid blue
# - Buttons:
#     Green (GPIO24) cycles mode: OFF -> HEAT -> COOL -> OFF
#     Red   (GPIO25) increases setpoint by 1F
#     Blue  (GPIO12) decreases setpoint by 1F
# - UART output every 30 seconds:
#     "<state>,<tempF>,<setpointF>"
#
# Note:
# Run with sudo because GPIO / serial access typically requires it:
#   sudo python3 Thermostat.py
#
# ------------------------------------------------------------------
# Change History
# ------------------------------------------------------------------
# Version   |   Description
# ------------------------------------------------------------------
#    1      Initial Development (course template)
#    2      Completed all TODO sections + safety cleanup + formatting
# ------------------------------------------------------------------

from time import sleep
from datetime import datetime

from statemachine import StateMachine, State

import board
import adafruit_ahtx0

import digitalio
import adafruit_character_lcd.character_lcd as characterlcd

import serial

from gpiozero import Button, PWMLED
from threading import Thread
from math import floor

DEBUG = True

# -----------------------------
# Hardware setup
# -----------------------------
i2c = board.I2C()
thSensor = adafruit_ahtx0.AHTx0(i2c)

ser = serial.Serial(
    port="/dev/ttyS0",         # /dev/ttyAMA0 on some older setups
    baudrate=115200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

redLight = PWMLED(18)
blueLight = PWMLED(23)


# -----------------------------
# LCD display manager
# -----------------------------
class ManagedDisplay:
    def __init__(self):
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)

        self.lcd_columns = 16
        self.lcd_rows = 2

        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en,
            self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7,
            self.lcd_columns, self.lcd_rows
        )
        self.lcd.clear()

    def cleanupDisplay(self):
        self.lcd.clear()
        self.lcd_rs.deinit()
        self.lcd_en.deinit()
        self.lcd_d4.deinit()
        self.lcd_d5.deinit()
        self.lcd_d6.deinit()
        self.lcd_d7.deinit()

    def clear(self):
        self.lcd.clear()

    def updateScreen(self, message: str):
        # Ensure we never overflow the LCD’s internal expectations
        self.lcd.clear()
        self.lcd.message = message


screen = ManagedDisplay()


# -----------------------------
# Thermostat state machine
# -----------------------------
class TemperatureMachine(StateMachine):
    "A state machine designed to manage our thermostat"

    off = State(initial=True)
    heat = State()
    cool = State()

    setPoint = 72  # Fahrenheit default

    cycle = (
        off.to(heat) |
        heat.to(cool) |
        cool.to(off)
    )

    # Thread control
    endDisplay = False

    def on_enter_heat(self):
        self.updateLights()
        if DEBUG:
            print("* Changing state to HEAT")

    def on_exit_heat(self):
        # Stop red pulsing when leaving HEAT
        redLight.off()

    def on_enter_cool(self):
        self.updateLights()
        if DEBUG:
            print("* Changing state to COOL")

    def on_exit_cool(self):
        # Stop blue pulsing when leaving COOL
        blueLight.off()

    def on_enter_off(self):
        redLight.off()
        blueLight.off()
        if DEBUG:
            print("* Changing state to OFF")

    def processTempStateButton(self):
        if DEBUG:
            print("Cycling Temperature State")
        self.cycle()        # state transition
        self.updateLights() # refresh indicators immediately

    def processTempIncButton(self):
        if DEBUG:
            print("Increasing Set Point")
        self.setPoint += 1
        self.setPoint = min(self.setPoint, 90)  # reasonable upper bound
        self.updateLights()

    def processTempDecButton(self):
        if DEBUG:
            print("Decreasing Set Point")
        self.setPoint -= 1
        self.setPoint = max(self.setPoint, 40)  # reasonable lower bound
        self.updateLights()

    def getFahrenheit(self) -> float:
        c = thSensor.temperature
        return ((9 / 5) * c) + 32

    def updateLights(self):
        """
        Update LEDs based on current thermostat state and temperature vs setPoint.
        """
        temp = floor(self.getFahrenheit())

        # Hard stop first so we don't overlap effects
        redLight.off()
        blueLight.off()

        if DEBUG:
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint}")
            print(f"Temp: {temp}")

        # OFF: both off
        if self.current_state == self.off:
            redLight.off()
            blueLight.off()
            return

        # HEAT behavior
        if self.current_state == self.heat:
            # If below setpoint, pulse red, else solid red
            if temp < self.setPoint:
                redLight.pulse(fade_in_time=0.8, fade_out_time=0.8, background=True)
            else:
                redLight.value = 1.0
            blueLight.off()
            return

        # COOL behavior
        if self.current_state == self.cool:
            # If above setpoint, pulse blue, else solid blue
            if temp > self.setPoint:
                blueLight.pulse(fade_in_time=0.8, fade_out_time=0.8, background=True)
            else:
                blueLight.value = 1.0
            redLight.off()
            return

    def setupSerialOutput(self) -> str:
        """
        Create the UART output string:
        "<state>,<tempF>,<setpointF>"
        """
        state = self.current_state.id.upper()
        temp = floor(self.getFahrenheit())
        output = f"{state},{temp},{self.setPoint}"
        return output

    def run(self):
        myThread = Thread(target=self.manageMyDisplay, daemon=True)
        myThread.start()

    def _fit16(self, s: str) -> str:
        """
        Fit exactly 16 characters for LCD line output.
        """
        s = s[:16]
        return s.ljust(16)

    def manageMyDisplay(self):
        counter = 1
        altCounter = 1

        # Ensure lights start correct even before first 10-sec refresh
        self.updateLights()

        while not self.endDisplay:
            if DEBUG:
                print("Processing Display Info...")

            current_time = datetime.now()

            # Line 1: date/time (fit to 16 chars)
            # Example style: "12/07 17:43:26"
            lcd_line_1 = self._fit16(current_time.strftime("%m/%d %H:%M:%S")) + "\n"

            # Line 2 alternates:
            if altCounter < 6:
                # Show current temperature
                temp_f = floor(self.getFahrenheit())
                lcd_line_2 = self._fit16(f"Temp:{temp_f:>3}F")
                altCounter += 1
            else:
                # Show mode + setpoint
                mode = self.current_state.id.upper()
                lcd_line_2 = self._fit16(f"{mode} SP:{self.setPoint:>3}F")
                altCounter += 1

                if altCounter >= 11:
                    # Refresh LEDs every ~10 seconds to keep behavior smooth
                    self.updateLights()
                    altCounter = 1

            screen.updateScreen(lcd_line_1 + lcd_line_2)

            if DEBUG:
                print(f"Counter: {counter}")

            # Send UART every 30 seconds
            if (counter % 30) == 0:
                msg = self.setupSerialOutput() + "\n"
                try:
                    ser.write(msg.encode("utf-8"))
                    if DEBUG:
                        print(f"UART -> {msg.strip()}")
                except Exception as e:
                    if DEBUG:
                        print(f"UART write failed: {e}")
                counter = 1
            else:
                counter += 1

            sleep(1)

        # Cleanup display when we stop
        screen.cleanupDisplay()


# -----------------------------
# Start thermostat
# -----------------------------
tsm = TemperatureMachine()
tsm.run()

# Buttons
greenButton = Button(24)
greenButton.when_pressed = tsm.processTempStateButton

redButton = Button(25)
redButton.when_pressed = tsm.processTempIncButton

blueButton = Button(12)
blueButton.when_pressed = tsm.processTempDecButton

repeat = True
while repeat:
    try:
        sleep(30)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        tsm.endDisplay = True
        sleep(1)
        try:
            ser.close()
        except Exception:
            pass
