
# Initialise the root level logger. All subsequent loggers will be the child of this logger,
# and will inherit the settings.
import logging
import sys


logging.basicConfig(
    stream=sys.stdout,
    format="('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s",
    level=logging.DEBUG)

log = logging.getLogger("socketio")
log.setLevel(logging.ERROR)

log = logging.getLogger("botocore")
log.setLevel(logging.ERROR)

# # Flask app will use this logger by default in its HTTP requests. Set it to logging.ERROR so that the
# # /poll requests and response wont flood the console.
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

#
# global tello
# global poseapp
# tello = None
# poseapp = None
# try:
#     print("Initializing tello and pose application server...\n")
#
#     tello = Tello("192.168.10.2", 8888, imperial=False, command_timeout=0.3)
#     tello.init_connection()
#     poseapp = PoseApp(delay_time=200, tello = tello)
#
#     # hub = Tello_Hub(CONNECTIONSTRING,PROTOCOL)
#     # hub.start_tello_updates_to_hub_thread()
#
#     import atexit
#     atexit.register(tello.__del__)
#
# except OSError as e:
#     logging.warning("Tello is not connected.")
#
# except RuntimeError as e:
#     logging.warning(str(e))
#
# except Exception as e:
#     logging.error("Exception Occurred: {}".format(traceback.format_exc()))
