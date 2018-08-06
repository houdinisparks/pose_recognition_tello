import logging
import subprocess
import threading
import traceback
from io import StringIO

import cv2
import itertools
import sys
from flask import Flask, render_template, Response, request
from flask_socketio import SocketIO, send, emit
from jinja2 import Environment, FileSystemLoader
import time
# from src import tello, poseapp, PoseApp
from src.poseapp.poseapp_kinesis import PoseAppWKinesis
from src.poseapp.poseapp_sockets import PoseAppWSockets
from src.utilities.tello import Tello

app = Flask(__name__, template_folder="static")
socketio = SocketIO(app)
processing_started = False
logger = logging.getLogger(__name__)

tello = Tello("192.168.10.2", 8888, imperial=False, command_timeout=0.3)
poseapp = PoseAppWSockets(delay_time=160, tello=tello)


# poseapp = PoseAppWKinesis(delay_time=500, tello=tello,produce_stream_name="poserec_raw",
#                           consumer_stream_name="poserec_results")


@app.route("/stream_events")
def stream_event():
    if request.headers.get('accept') == 'text/event-stream':
        def events():
            for i, c in enumerate(itertools.cycle('\|/-')):
                yield "data: %s %d\n\n" % (c, i)
                time.sleep(.1)  # an artificial delay

        return Response(events(), content_type='text/event-stream')
    return "Error"


@app.route('/')
def index():
    return Response(render_template("index.html"))


@app.route("/start", methods=['POST'])
def start():
    # todo: start processings
    global poseapp
    global processing_started

    if not processing_started:

        try:
            server_add = request.form["server_add"]
            poseapp.start(remote_server_ip=server_add)
            processing_started = True

        except Exception as e:

            logger.error(traceback.format_exc())
            return Response("internal server error: try again", status=500)

        return "started processing"
    else:
        return "already started"


@app.route("/stop", methods=['POST'])
def stop():
    global processing_started
    try:

        processing_started = False
        poseapp.stop()

    except Exception as e:
        logging.error(traceback.format_exc())
        return Response("unable to stop. error occurred.", status=500)

    return "stopped"


@app.route("/camera_feed")
def camera_feed():
    def gen_feed():
        fps_time = time.time()
        # while True and not poseapp.start_th_signal.wait(poseapp.delay_time / 1000):
        while True and not poseapp.start_th_signal.is_set():
            frame = poseapp.frame_processed_queue.get(block=True)
            ret, jpeg = cv2.imencode('.jpg', frame)
            # logger.debug("video fps %s" % (1.0 / (time.time() - fps_time)))
            fps_time = time.time()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

        logger.info("Videostream closed.")

    return Response(gen_feed(), mimetype='multipart/x-mixed-replace; boundary=frame')


thread = None
thread_lock = threading.Lock()


# def scheduled task to emit
def background_thread():
    while True:
        socketio.sleep(3)
        resp = {}
        if tello.state != "disconnected":
            resp = {"tello_state": tello.state,
                    "tello_battery": tello.battery,
                    "tello_speed": tello.speed,
                    "tello_flight_time": tello.flight_time}
        else:
            resp = {"tello_state": tello.state,
                    "tello_battery": "disconnected",
                    "tello_speed": "disconnected",
                    "tello_flight_time": "disconnected"}

        socketio.emit('tello_state', resp, broadcast=True)


@socketio.on('connect')
def test_connect():
    logger.info("Websockets connected..Sending info on tello_connect_state on background thread...")
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)


@app.route("/connect_tello", methods=["POST"])
def tello_connect():
    try:
        poseapp.init_tello_connection()
        return "Connected."
    except Exception as e:
        return Response(str(e), status=500)

@app.route("/change_reso/<int:value>", methods=["POST"])
def change_reso(value=436):
    poseapp.res_w = value
    return "value changes to {}".format(value)

# # when websocket receive named event, send info
# @socketio.on("tello_connect_state")
# def connect_tello(message):
#     emit("tello_state", tello.state)

if __name__ == "__main__":
    # app.run(debug=True, port=5001)
    socketio.run(app, debug=True, port=5001, use_reloader=False)
    # def stream_log():
    #     while True:
    #         line = mystdout.readline()
    #         mystdout.seek(len(line))
    #         yield line.rstrip() + '\n'
    #
    #         # for line in mystdout.readline():
    #         #     yield line.rstrip() + '<br/>\n'
    #         #
    #         # # print(mystdout.getvalue())
    #         # # for line in mystdout.getvalue():
    #         # #     # time.sleep(1)  # Don't need this just shows the text streaming
    #         # #     yield line.rstrip() + '<br/>\n'
    #         # yield mystdout.getvalue()
    #         # #     time.sleep(4)  # Don't need this just shows the text streaming
    #         # #     yield i

    # env = Environment(loader=FileSystemLoader('static'))
    # tmpl = env.get_template('console.html')
    # return Response(tmpl.generate(
    #     img_byte_array=gen_feed()))
    # return Response(gen_feed(),
    #                 mimetype='multipart/x-mixed-replace; boundary=frame')
