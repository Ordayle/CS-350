#
# SerialLightControl-Server.py - This is the code to complete
# Milestone Two.
# 
# This Python code will be used to control the light in the circuit 
# that you built on your solderless breadboard in Milestone One based 
# on the instructions read from the serial port of your Raspberry pi.
#
# This script requires that you have correctly configured your Serial
# port and have a USB -> TTL cable connected appropriately.
#
#------------------------------------------------------------------
# Change History
#------------------------------------------------------------------
# Version   |   Description
#------------------------------------------------------------------
#    1          Initial Development
#------------------------------------------------------------------

# This imports the Python serial package to handle communications over the
# Raspberry Pi's serial port. 
import serial

# Load the GPIO interface from the Raspberry Pi Python Module
# The GPIO interface will be available through the GPIO object
import RPi.GPIO as GPIO

# Because we imported the entire package instead of just importing Serial and
# some of the other flags from the serial package, we need to reference those
# objects with dot notation.
#
# e.g. ser = serial.Serial
#
ser = serial.Serial(
        port='/dev/ttyS0', # This would be /dev/ttyAM0 prior to Raspberry Pi 3
        baudrate = 115200, # This sets the speed of the serial interface in
                           # bits/second
        parity=serial.PARITY_NONE,      # Disable parity
        stopbits=serial.STOPBITS_ONE,   # Serial protocol will use one stop bit
        bytesize=serial.EIGHTBITS,      # We are using 8-bit bytes 
        timeout=1          # Configure a 1-second timeout
)

# Setup the GPIO interface
#
# 1. Turn off warnings for now - they can be useful for debugging more
#    complex code.
# 2. Tell the GPIO library we are using Broadcom pin-numbering. The 
#    Raspberry Pi CPU is manufactured by Broadcom, and they have a 
#    specific numbering scheme for the GPIO pins. It does not match
#    the layout on the header. However, the Broadcom pin numbering is
#    what is printed on the GPIO Breakout Board, so this should match!
# 3. Tell the GPIO library that we are using GPIO line 18, and that 
#    we are using it for Output. When this state is configured, setting
#    the GPIO line to true will provide positive voltage on that pin.
#    Based on the circuit we have built, positive voltage on the GPIO
#    pin will flow through the LED, through the resistor to the ground
#    pin and the LED will light up. 
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)

# Configure our loop variable
repeat = True

# Loop until the user hits CTRL-C or the client sends an exit/quit message
while repeat:
    try:
        # Read one line of text from the serial port.
        # This blocks until data is available.
        # We decode bytes into a UTF-8 string, ignore any malformed bytes,
        # convert to lowercase, and strip whitespace/newlines.
        command = ser.readline().decode("utf-8", errors="ignore").lower().strip()

        # If we received an empty string (noise, blank line), skip this loop cycle
        if not command:
            continue

        # State-machine style control — take action based on the command value
        match command:

            case "off":
                # Set GPIO pin 18 LOW (0V)
                # This turns OFF the LED or any device attached to that pin.
                GPIO.output(18, False)

            case "on":
                # Set GPIO pin 18 HIGH (3.3V)
                # This turns ON the LED or any device attached to that pin.
                GPIO.output(18, True)

            case "exit" | "quit":
                # Before exiting, ensure the LED is turned off
                GPIO.output(18, False)
                # Clean up the GPIO resources safely
                GPIO.cleanup()
                # End the repeat loop (do not use 'break' to keep structure clean)
                repeat = False

            case _:
                # Any unknown or unsupported command is ignored gracefully
                pass

    except KeyboardInterrupt:
        # CTRL-C pressed — exit the program cleanly
        GPIO.output(18, False)   # Ensure LED is OFF
        GPIO.cleanup()           # Release GPIO pins
        repeat = False           # Stop loop




                
