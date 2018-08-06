import argparse
import concurrent
import copy
import logging

import os
import pickle
import socket

import struct
import threading
import traceback
from concurrent import futures
from queue import Queue, Empty

import asyncio
import sys
import time

import cv2
from tf_pose import common
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import model_wh, get_graph_path
from src.poseapp.poseapp_sockets import PoseAppWSockets

import tensorflow as tf

logging.basicConfig(
    stream=sys.stdout,
    format="('%(threadName)s - %(levelname)s - %(message)s",
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Globals
n_workers = int(input("Number of workers for thread pool? "))

futures_q = Queue(maxsize=n_workers)
worker_mgr = None
th_signal = threading.Event()
process_th = None
send_th = None
exc_info = None
exc_thrown = False

estimator = TfPoseEstimator(get_graph_path("mobilenet_thin"), target_size=(432, 368),
                            tf_config=tf.ConfigProto(log_device_placement=True))

w, h = model_wh("432x368")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

HOST = '0.0.0.0'
PORT = 8089
conn = None
addr = None
connected = False


def wait_for_connection():
    global s, connected, conn , addr
    try:
        logger.info("Listening for connections...")
        s.listen(5)
        conn, addr = s.accept()
        conn.settimeout(5)  # raise exception if nothing is received in 4 secs.
        logger.info("Connected to {}\nStart video processing.".format(addr))
        connected = True

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.info("Restarting..")
        wait_for_connection()




def _worker_th(frame):
    global estimator, w, h
    humans = estimator.inference(frame, resize_to_default=(w > 0 and h > 0), upsample_size=4.0)
    pose = "none"
    if len(humans) > 0:
        humans.sort(key=lambda x: x.score, reverse=True)
        humans = humans[:1]  # get the human with the highest score
        frame = TfPoseEstimator.draw_humans(frame, humans)
        frame, pose = PoseAppWSockets.identify_body_gestures(frame, humans[0])


    return frame, pose


def _send_th():
    logger.info("Sending thread started...")
    global conn, exc_info, exc_thrown
    global futures_q
    global th_signal
    fps_time = time.time()
    while True and not th_signal.is_set():
        try:
            future = futures_q.get(timeout=2)
            frame, pose = future.result(timeout=2)
            humans_data = pickle.dumps((frame, pose))
            conn.sendall(struct.pack("<L", len(humans_data)) + humans_data)
            # todo: problem! sendall will hang after some time. what seems to be the problem??

            # print("sent fps {0:.2f} q size {1}".format((1.0 / (time.time() - fps_time)), futures_q.qsize()))
            fps_time = time.time()

        except concurrent.futures.TimeoutError:
            logger.info("Waiting for worker thread to complete frame to send.")
            continue

        except ZeroDivisionError:
            logger.error("FPS division error")
            continue

        except Empty:
            logger.warning("Future queue is empty.")
            continue

        except Exception as ex:
            logger.info(
                "Exception caught in send thread, raising to main thread... \n{}".format(traceback.format_exc()))
            exc_info = sys.exc_info()
            exc_thrown = True
            continue


def exit_connection():
    global conn
    global send_th
    global futures_q, worker_mgr
    global connected, exc_info

    try:
        conn.close()
        logger.info("Closing socket...")
    except:
        logger.error("Error closing socket {}".format(traceback.format_exc()))

    # close process threads
    if not th_signal.is_set():
        th_signal.set()
        send_th.join()
        logger.info("Sending thread closed.")

    # wait and clear all pending futures
    logger.info("Shutting down thread pool executor...")
    worker_mgr.shutdown(wait=False)

    logger.info("Clearing futures queue...")
    with futures_q.mutex:
        futures_q.queue.clear()

    connected = False


def start_threads():
    global worker_mgr, n_workers, send_th, th_signal, exc_info, exc_thrown
    exc_info = None
    exc_thrown = False
    th_signal.clear()
    logger.info("Initialising thread pool with {} workers".format(n_workers))
    worker_mgr = futures.ThreadPoolExecutor(max_workers=n_workers)
    send_th = threading.Thread(target=_send_th)
    send_th.start()


if __name__ == "__main__":

    s.bind((HOST, PORT))
    logger.info("Socket successfuly created and binded to {0}:{1}".format(HOST, PORT))

    fps_time = 0
    payload_size = struct.calcsize("<L")

    while True:
        if not connected:
            wait_for_connection()
            start_threads()
            data = b""

        else:
            try:
                if exc_thrown:
                    logger.error("Exception caught in send thread, breaking the connection..")
                    raise exc_info[1].with_traceback(exc_info[2])

                # logger.error("1")
                while len(data) < payload_size:
                    data += conn.recv(8196)
                    if not data:
                        raise RuntimeError("no data received, closing connection, listening for new connection")
                packed_msg_size = data[:payload_size]
                msg_size = struct.unpack("<L", packed_msg_size)[0]  # of bytes in frame.

                # Get the frame data itself into data var.
                data = data[payload_size:]
                # logger.info("Frame received. Size: {}".format(msg_size))
                while len(data) < msg_size:
                    data += conn.recv(8196)
                    if not data:
                        raise RuntimeError("no data received, closing connection, listening for new connection")
                # logger.info("2")

                frame_data = data[:msg_size]
                data = data[msg_size:]

                # Convert the frame data back to its original form.
                frame = pickle.loads(frame_data)

                # Submit frame to worker thread for processing
                future = worker_mgr.submit(_worker_th, frame)
                futures_q.put(future)
                # logger.info("3")
            except Exception as e:
                logger.error("Exception caught! {}".format(traceback.format_exc()))
                exit_connection()
                continue
