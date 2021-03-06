import serial
import RPi.GPIO as GPIO
import time

# Global Constants
CONVERSION_FACTOR_TURN = 2.22 #steps per degree
CONVERSION_FACTOR_TILT = 10.0 #steps per degree

class Robot(object):
    """
    Object to control Minitaur Robot that reacts to 8 byte integer 
    command.
    """
    
    def __init__(self):
        # Setting time to pause between steps of stepper motor
        self.MOTOR_DELAY = 0.01 #sec

        # setup pins for rotation
        self.STEP_PIN_TURN = 2
        self.STEP_PIN_TILT = 14
        self.DIRECTION_PIN_TURN = 3
        self.DIRECTION_PIN_TILT = 15
        self.ENABLE_PIN_TURN = 4
        self.ENABLE_PIN_TILT = 17

        # starting head position
        self.turn_angle = 0 #deg
        self.tilt_angle = 0 #deg
        self.turn_steps = 0 # count of steps from neutral
        self.tilt_steps = 0 # count of steps from neutral

        return

    def connect(self, usb_port_address, bauderate, time_out = 1, head = True):
        """
        Sets up the initial serial communication connection
        """
        self.ser = serial.Serial(usb_port_address,
                                bauderate, 
                                timeout = time_out)
        
        if head:
            # Head control via pin communicatoin
            GPIO.setmode(GPIO.BCM)
            ## motor 1: turning
            GPIO.setup(self.STEP_PIN_TURN, GPIO.OUT)
            GPIO.setup(self.DIRECTION_PIN_TURN, GPIO.OUT)
            GPIO.setup(self.ENABLE_PIN_TURN, GPIO.OUT)
            ## motor 2: tilting
            GPIO.setup(self.STEP_PIN_TILT, GPIO.OUT)
            GPIO.setup(self.DIRECTION_PIN_TILT, GPIO.OUT)
            GPIO.setup(self.ENABLE_PIN_TILT, GPIO.OUT)

            ## connecting to motors
            GPIO.output(self.ENABLE_PIN_TURN,GPIO.LOW)
            GPIO.output(self.ENABLE_PIN_TILT,GPIO.LOW)

        return
    
    def disconnect(self):
        """
        Disconnects the serial communication.
        """
        self.ser.close()
        GPIO.cleanup()

#--------------------------------------------------------------------
# Body Control
#--------------------------------------------------------------------

    def __convertToCommand(self, float_in):
        """
        Takes in command in float form and encodes command as two digit string.
        """
        int_in = int(float_in * 10)
        first_digit = 0 if int_in < 0 else 1    #encodes negative
        second_digit = abs(int_in)              #only consider magnitude
        return (first_digit, second_digit)

    def command(self, **kwargs):
        """
        Controls main body translation.
        Converts command input to 8 byte integer.
        Takes arguments as follows:
            behavior    [int]                      0 to 9,
            forward     [m/s]                   -0.9 to 0.9,
            turn        [rad/s]                 -0.9 to 0.9,
            height      [% relative to normal]  -0.9 to 0.9
        """
        new_command = list("90000000")

        for key in kwargs:
            if key == 'forward':
                new_command[2:4] = self.__convertToCommand(kwargs[key])
            elif key == 'turn':
                new_command[4:6] = self.__convertToCommand(kwargs[key])
            elif key == 'height':
                new_command[6:8] = self.__convertToCommand(kwargs[key])
            elif key == 'behavior':
                new_command[1] = int(kwargs[key])

        new_command = map(str,new_command) # converting int to char
        new_command = ''.join(new_command) # joining char to str

        # Waiting for Signal that Minitaur is ready to receive command input
        read = None
        while(read != b'next\n'):
            read = self.ser.readline()
            print(read)
        
        # Sending new command string
        print(">>> Sent: " + str(new_command))
        self.ser.write(str.encode(str(new_command)))


#--------------------------------------------------------------------
# Head Unit Control
#--------------------------------------------------------------------
    def resetHeadPosition(self):
        """
        Resets head to move to 0 deg turn and 0 deg tilt.
        --- Under development ---
        How do we know the position when we first run the 
        script?
        ----------------------------------------------
        """
        
        return 

    def __deg2step(self, degrees, CONVERSION_FACTOR):
        """
        Converts number of degrees to number of steps and step direction.
        --- Under development ---
        Add conversion factor: emperically determined.
        Check: Direction assumption
        ----------------------------------------------
        """
        # assuming that LOW goes left and HIGH turns right
        direction = GPIO.LOW if degrees <= 0 else GPIO.HIGH
        steps = round(CONVERSION_FACTOR*degrees,0) # rounding to next integer
        steps = abs(int(steps))                    # convert to positive int type
        return (direction,steps)


    def look(self, **kwargs):
        """ 
        --- Under development ---
        Add max degree safety feature
        -----------------------------
        Controls the field of vision by rotating head. 
        Takes arguments as follows:
        keyword:    [int] value
        tilt:       [deg]  -45 to 45 
        turn:       [deg] -160 to 160
        """
        steps_turn = 0
        direct_turn = None

        steps_tilt = 0
        direct_tilt = None

        for key in kwargs:
            if key == 'turn':
                if abs(kwargs[key]) > 160:
                    print("Degrees of head rotation out of bounds. \n Valid interval: [-135, 135]")
                    return
                degrees = kwargs[key] - self.turn_angle
                direct_turn, steps_turn = self.__deg2step(degrees, CONVERSION_FACTOR_TURN)
                self.turn_steps = self.turn_steps + (-1*steps_turn) \
                                if degrees < 0 else self.turn_steps + steps_turn
                self.turn_angle = self.turn_steps / CONVERSION_FACTOR_TURN
            elif key == 'tilt':
                if abs(kwargs[key]) > 45:
                    print("Degrees of head rotation out of bounds. \n Valid interval: [-135, 135]")
                    return
                degrees = kwargs[key] - self.tilt_angle
                direct_tilt, steps_tilt = self.__deg2step(degrees, CONVERSION_FACTOR_TILT)
                self.tilt_steps = self.tilt_steps + (-1*steps_tilt) \
                                if degrees < 0 else self.tilt_steps + steps_tilt
                self.tilt_angle = self.tilt_steps / CONVERSION_FACTOR_TILT   
            else:
                print("ERROR: Invalid command input.")

        print(">>> Moving head to new position <<<")

        # Choosing max steps value
        steps = steps_turn if steps_turn > steps_tilt else steps_tilt

        # Setting direction
        GPIO.output(self.DIRECTION_PIN_TURN,direct_turn)
        GPIO.output(self.DIRECTION_PIN_TILT,direct_tilt)

        print("Turning table by %.1f steps"%steps_turn)
        print("Tilting mount by %.1f steps"%steps_tilt)

        # Sending signal to motors
        for i in range(steps):
            if i < steps_turn:
                GPIO.output(self.STEP_PIN_TURN,GPIO.LOW)
            if i < steps_tilt:
                GPIO.output(self.STEP_PIN_TILT,GPIO.LOW)
            time.sleep(self.MOTOR_DELAY)
            if i < steps_turn:
                GPIO.output(self.STEP_PIN_TURN,GPIO.HIGH)
            if i < steps_tilt:
                GPIO.output(self.STEP_PIN_TILT,GPIO.HIGH)
            time.sleep(self.MOTOR_DELAY)
        print(">>> Head arrived at target position <<<")
        return


    
if __name__ == '__main__':
    """
    Test routine: 
     -  walk forward 3sec and rotate head slightly up and right, 
     -  walk at higher standing height normal height 2sec 
            and turn head to starting position, 
     -  sit 2 sec,
     -  return to starting position
    """
    # different for every computer
    PORT = '/dev/ttyUSB0' # Realsense CPU
    # PORT = '/dev/tty.usbserial-DN01QALN' # Jan's MB
    BAUDERATE = 115200
    TIMEOUT = 1
    obj = Robot()
    obj.connect(PORT,BAUDERATE,TIMEOUT)
    try:
        print(" >>> START TEST SEQUENCE <<<")
        print(">>> WALK & LOOK SLIGHTLY RIGHT, UP <<<")
        obj.look(turn=90,tilt=35)
        for _ in range(30):
            obj.command(forward=0.3)
            time.sleep(0.1)
        print(">>> HIGH WALK & LOOK FROM INITIAL POSITION <<<")
        obj.look(turn=0,tilt=0)
        for _ in range(20):
            obj.command(forward=0.2,height=0.3)
            time.sleep(0.1)
        print(">>> SIT <<<")
        for _ in range (20):
            obj.command(height = -.9)
            time.sleep(0.1)
        print(">>> STAND <<<")
        for _ in range (20):
            obj.command()
            time.sleep(0.1)
        
        obj.disconnect()
        print(">>> TEST COMPLETE <<<")
        
    except KeyboardInterrupt:
        obj.disconnect()    
        print("Test ended prematurely and has been disconnected")
