"""License.
Copyright 2018 Todd Mueller <firstnamelastname@gmail.com>
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import socket
import threading
from enum import Enum

import time
import traceback
import logging

logger = logging.getLogger(__name__)


class Tello:
    """Wrapper to simply interactions with the Ryze Tello drone."""

    def __init__(self, local_ip, local_port, imperial=True, command_timeout=.3, tello_ip='192.168.10.1',
                 tello_port=8889):
        """Binds to the local IP/port and puts the Tello into command mode.
        Args:
            local_ip (str): Local IP address to bind.
            local_port (int): Local port to bind.
            imperial (bool): If True, speed is MPH and distance is feet.
                             If False, speed is KPH and distance is meters.
            command_timeout (int|float): Number of seconds to wait for a response to a command.
            tello_ip (str): Tello IP.
            tello_port (int): Tello port.
        Raises:
            RuntimeError: If the Tello rejects the attempt to enter command mode.
        """

        self.abort_flag = False
        self.command_timeout = command_timeout
        self.imperial = imperial
        self.response = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.local_address = None
        self.tello_address = (tello_ip, tello_port)

        self.send_command_interval = 2
        self.last_epoch = 0

        self._battery = 0
        self._flight_time = 0
        self._speed = 0

        # Async thread to receive responses from tello
        self.receive_thread = None
        # self.receive_thread.daemon = True
        # self.receive_thread.start()

        self.id = 1  # todo: configure this part

        # # Async thread to populate flight details of tello
        self.update_tello_details_thread = None
        # self.update_tello_details_thread.daemon = True
        # self.update_tello_details_thread.start()

        self._state = "disconnected"

    def __del__(self):
        """Closes the local socket."""

        self.socket.close()

    def init_connection(self):
        if self.state == "disconnected":
            # self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # self.socket.bind((self.local_address[0], self.local_address[1]))

            self.socket.connect(self.tello_address)
            local_address = self.socket.getsockname()
            if "192.168.10" not in local_address[0]:
                raise RuntimeError("Please check if you have connected the tello on wifi.")

            self.local_address = local_address
            self.receive_thread = threading.Thread(target=self._receive_thread)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            if self.send_command('command') != 'OK':
                self._state = "disconnected"

            else:
                self._state = "connected"

                # Async thread to populate flight details of tello
                self.update_tello_details_thread = threading.Thread(target=self._update_tello_details_thread)
                self.update_tello_details_thread.daemon = True
                self.update_tello_details_thread.start()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if self._state != value:
            logger.info(str(value))
        self._state = value

    # def delete_tello(self):
    @property
    def flight_time(self):
        return self._flight_time

    @flight_time.setter
    def flight_time(self, value):
        self._flight_time = value

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def battery(self):
        return self._battery

    @battery.setter
    def battery(self, value):
        self._battery = value

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        self._speed = value

    def _receive_thread(self):
        """Listens for responses from the Tello.
        Runs as a thread, sets self.response to whatever the Tello last returned.
        """
        while True:
            try:
                self.response, ip = self.socket.recvfrom(256)

            except socket.timeout as e:
                break

            except Exception as e:
                logger.error("Exception caught in {}".format(traceback.format_exc()))
                break

    def _update_tello_details_thread(self):
        """
        Pings tello for battery, flight time and speed updates. Populates
        the properties for other classes to use.
        :return:
        """
        try_again_count = 0
        while True:
            try:
                self.battery = self.get_battery()
                self.speed = self.get_speed()
                self.flight_time = self.get_flight_time()
                time.sleep(5)

            except Exception:
                # self.socket.close()
                logging.warning("Tello refuses to update tello details. Trying again... {}".format(try_again_count))
                try_again_count += 1
                if try_again_count == 2:
                    self.state = "disconnected"
                    logging.warning(
                        "Tello refuses to update tello details. Assume disconnected".format(try_again_count))
                    break
                # raise RuntimeError('Tello refuses to update tello details.')

    def flip(self, direction):
        """Flips.
        Args:
            direction (str): Direction to flip, 'l', 'r', 'f', 'b', 'lb', 'lf', 'rb' or 'rf'.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """

        return self.send_command('flip %s' % direction)

    def get_battery(self):
        """Returns percent battery life remaining.
        Returns:
            int: Percent battery life remaining.
        """

        battery = self.send_command('battery?')

        try:
            battery = int(battery)
        except:
            pass

        return battery

    def get_flight_time(self):
        """Returns the number of seconds elapsed during flight.
        Returns:
            int: Seconds elapsed during flight.
        """

        flight_time = self.send_command('time?')

        try:
            flight_time = int(flight_time)
        except:
            pass

        return flight_time

    def get_speed(self):
        """Returns the current speed.
        Returns:
            int: Current speed in KPH or MPH.
        """

        speed = self.send_command('speed?')

        try:
            speed = float(speed)

            if self.imperial is True:
                speed = round((speed / 44.704), 1)
            else:
                speed = round((speed / 27.7778), 1)
        except:
            pass

        return speed

    def land(self):
        """Initiates landing.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        self.state = "land"
        return self.send_command('land')

    def move(self, direction, distance):
        """Moves in a direction for a distance.
        This method expects meters or feet. The Tello API expects distances
        from 20 to 500 centimeters.
        Metric: .1 to 5 meters
        Imperial: .7 to 16.4 feet
        Args:
            direction (str): Direction to move, 'forward', 'back', 'right' or 'left'.
            distance (int|float): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        self.state = "going {0} by {1}m".format(direction, distance)

        distance = float(distance)

        if self.imperial is True:
            distance = int(round(distance * 30.48))
        else:
            distance = int(round(distance * 100))

        return self.send_command('%s %s' % (direction, distance))

    def move_backward(self, distance):
        """Moves backward for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """

        return self.move('back', distance)

    def move_down(self, distance):
        """Moves down for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """

        return self.move('down', distance)

    def move_forward(self, distance):
        """Moves forward for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        return self.move('forward', distance)

    def move_left(self, distance):
        """Moves left for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        return self.move('left', distance)

    def move_right(self, distance):
        """Moves right for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        """
        return self.move('right', distance)

    def move_up(self, distance):
        """Moves up for a distance.
        See comments for Tello.move().
        Args:
            distance (int): Distance to move.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """

        return self.move('up', distance)

    def send_command(self, command):
        """Sends a command to the Tello and waits for a response.
        If self.command_timeout is exceeded before a response is received,
        a RuntimeError exception is raised.
        Args:
            command (str): Command to send.
        Returns:
            str: Response from Tello.
        Raises:
            RuntimeError: If no response is received within self.timeout seconds.
        """

        # while time.time() - self.last_epoch > self.send_command_interval:
        #     pass

        self.abort_flag = False
        timer = threading.Timer(self.command_timeout, self.set_abort_flag)

        self.socket.sendto(command.encode('utf-8'), self.tello_address)
        self.last_epoch = time.time()
        timer.start()

        while self.response is None:
            if self.abort_flag is True:
                raise RuntimeError('No response to command. Check Tello connection.')

        timer.cancel()

        response = self.response.decode('utf-8')
        logger.info("Command Sent to Tello {0}, with response: {1}".format(
            command, response
        ))
        self.response = None

        return response

    def set_abort_flag(self):
        """Sets self.abort_flag to True.
        Used by the timer in Tello.send_command() to indicate to that a response
        timeout has occurred.
        """

        self.abort_flag = True

    def set_speed(self, speed):
        """Sets speed.
        This method expects KPH or MPH. The Tello API expects speeds from
        1 to 100 centimeters/second.
        Metric: .1 to 3.6 KPH
        Imperial: .1 to 2.2 MPH
        Args:
            speed (int|float): Speed.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """

        speed = float(speed)

        if self.imperial is True:
            speed = int(round(speed * 44.704))
        else:
            speed = int(round(speed * 27.7778))

        return self.send_command('speed %s' % speed)

    def takeoff(self):
        """Initiates take-off.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        self.state = "takeoff"

        return self.send_command('takeoff')

    def rotate_cw(self, degrees):
        """Rotates clockwise.
        Args:
            degrees (int): Degrees to rotate, 1 to 360.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        self.state = "rotate_cw"

        return self.send_command('cw %s' % degrees)

    def rotate_ccw(self, degrees):
        """Rotates counter-clockwise.
        Args:
            degrees (int): Degrees to rotate, 1 to 360.
        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.
        """
        self.state = "rotate_ccw"
        return self.send_command('ccw %s' % degrees)
