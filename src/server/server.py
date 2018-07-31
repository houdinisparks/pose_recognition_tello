import argparse
import copy
import logging

import os
import pickle
import socket

import struct
import threading
import traceback
from queue import Queue, Empty

import sys
import time

import cv2
from tf_pose import common
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import model_wh, get_graph_path

logging.basicConfig(
    stream=sys.stdout,
    format="('%(threadName)s - %(levelname)s - %(message)s",
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Globals
recv_queue = Queue()
processed_queue = Queue()
th_signal = threading.Event()
process_th = None
send_th = None

estimator = TfPoseEstimator(get_graph_path("mobilenet_thin"), target_size=(432, 368))
w, h = model_wh("432x368")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

HOST = '0.0.0.0'
PORT = 8089
conn = None
addr = None
connected = False

def wait_for_connection():
    global s, connected
    logger.info("Listening for connections...")
    s.listen(5)
    conn, addr = s.accept()
    conn.settimeout(4)  # raise exception if nothing is received in 4 secs.
    logger.info("Connected to {}\nStart video processing.".format(addr))
    connected = True


    return conn, addr


def _process_th():
    logger.info("Prcessing thread started...")
    global th_signal
    global recv_queue
    global estimator, w, h
    while True and not th_signal.is_set():
        try:
            frame = recv_queue.get(timeout=2)
            humans = estimator.inference(frame, resize_to_default=(w > 0 and h > 0), upsample_size=4.0)
            futures_q.put(humans)

        except Empty:
            logger.info("Processed queue empty.")
            continue


def _send_th():
    logger.info("Sending thread started...")
    global conn
    global processed_queue
    global th_signal
    fps_time = time.time()
    while True and not th_signal.is_set():
        try:
            humans = processed_queue.get(timeout=2)
            humans_data = pickle.dumps(humans)
            conn.sendall(struct.pack("<L", len(humans_data)) + humans_data)
            logger.info("human joints ps sent %s" % (1.0 / (time.time() - fps_time)))
            fps_time = time.time()
        except Empty:
            logger.info("Sending queue empty.")
            continue

        except ZeroDivisionError:
            logger.error("FPS division error")
            continue

        except Exception as ex:
            logger.info("Exception occurred: {}".format(traceback.format_exc()))
            break


def exit_connection():
    global conn
    global process_th, send_th
    global recv_queue, futures_q
    global connected

    conn.shutdown(2)
    conn.close()
    logger.info("Closing socket...")

    # close process threads
    if not th_signal.is_set():
        th_signal.set()
        send_th.join()
        logger.info("Sending thread closed.")
        process_th.join()
        logger.info("Processing thread closed.")

    # empty all queues
    with recv_queue.mutex:
        recv_queue.queue.clear()

    with processed_queue.mutex:
        processed_queue.queue.clear()

    connected = False


def start_threads():
    global process_th, send_th, th_signal
    th_signal.clear()
    process_th = threading.Thread(target=_process_th)
    process_th.start()
    send_th = threading.Thread(target=_send_th)
    send_th.start()

    #todo: start max 5 threads for processing


if __name__ == "__main__":

    s.bind((HOST, PORT))
    logger.info("Socket successfuly created and binded to {0}:{1}".format(HOST, PORT))

    fps_time = 0
    payload_size = struct.calcsize("<L")

    while True:
        if not connected:
            conn, addr = wait_for_connection()
            start_threads()
            data = b""

        else:
            try:
                while len(data) < payload_size:
                    data += conn.recv(65536)

                    if not data:
                        raise RuntimeError("no data received, closing connection, listening for new connection")
                packed_msg_size = data[:payload_size]
                msg_size = struct.unpack("<L", packed_msg_size)[0]  # of bytes in frame.

                # Get the frame data itself into data var.
                data = data[payload_size:]
                logger.info("payload received. size: {}".format(msg_size))
                while len(data) < msg_size:
                    data += conn.recv(65536)
                    if not data:
                        raise RuntimeError("no data received, closing connection, listening for new connection")

                frame_data = data[:msg_size]
                data = data[msg_size:]

                # Convert the frame data back to its original form.
                frame = pickle.loads(frame_data)
                recv_queue.put(frame)

            except Exception as e:
                logger.warning(str(e))
                exit_connection()
                continue

