# Sending and receiving data streams for server
import logging
import socket
import threading
import traceback
import time
import struct
from queue import Queue

import pickle

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class FrameSocketStream():

    def __init__(self, serverip, port):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._serverip = serverip
        self._port = port

        # Async thread to receive responses from server
        self.th_recv = None
        self.socket_is_closed = False

    @property
    def socket(self):
        return self._socket

    def init_connection(self):
        while True:
            try:
                self.socket.connect((self._serverip, int(self._port)))
                print("Connected to {}:{}".format(self._serverip, self._port))
                time.sleep(1)
                self.socket_is_closed = False
                self.socket.settimeout(2)
                break
            except Exception as e:
                logger.error("Exception caught {}".format(traceback.format_exc()))
                raise RuntimeError("Problem connecting to server")

    def start_recv_thread(self, recv_callback):
        self.th_recv_signal = threading.Event()
        self.th_recv = threading.Thread(target=self._th_recv, args=(recv_callback,))
        # self.th_recv.do_run = True
        # self.th_recv.daemon = True  # main thread and still exit even if this thread is running.
        self.th_recv.start()

    def _th_recv(self, callback):
        # t = threading.currentThread()
        data = b''
        payload_size = struct.calcsize("<L")
        while True and not self.th_recv_signal.is_set():
            try:

                while len(data) < payload_size:
                    data += self.socket.recv(8192)

                logger.debug("Frame size received. Size: {}\n".format(len(data)))
                packed_msg_size = data[:payload_size]
                human_payload_size = struct.unpack("<L", packed_msg_size)[0]  # of bytes in frame.

                # Get the human data
                data = data[payload_size:]
                while len(data) < human_payload_size:
                    data += self.socket.recv(8192)

                logger.debug("Frame received. Size: {}\n".format(len(data)))
            except socket.timeout:
                # this will auto close the socket.
                logger.info("Socket timeout at recv thread. Continuing...")
                continue

            except:
                logger.error("Exception occurred: {}\n\nConnection lost.".format(traceback.format_exc()))
                self.close_socket()
                break

            human_data = data[:human_payload_size]
            data = data[human_payload_size:]

            # Convert the frame and human data back to its original form.
            frame, pose = pickle.loads(human_data)

            # Put humans in receive queue for other objects to access.
            # self._recv_queue.put(humans, block=True)
            callback(frame, pose)

        logger.info("Exiting receiving thread.")

    def send(self, frame):

        try:
            # frame = self.send_queue.get()
            data = pickle.dumps(frame)
            self.socket.sendall(struct.pack("<L", len(data)) + data)
            # self.sent_queue.put(frame, block=True)

        except ZeroDivisionError:
            print("Exception caught: {}".format(traceback.format_exc()))

        except socket.timeout:
            logger.info("Socket timeout while sending. Continuing...")

        except Exception as e:
            print("Exception caught: {}".format(traceback.format_exc()))
            self.close_socket()
            # with self.sent_queue.mutex:
            #     self.sent_queue.queue.clear()

    def close_socket(self):

        try:
            if not self.th_recv_signal.is_set():
                self.th_recv_signal.set()
                self.th_recv.join()  # block until recv thread succ terminates
                logger.info("Socket receive thread successfully stopped.")
        except RuntimeError as e:
            logger.error("Error joinging thread. Continue attempt to close socket.")

        if not self.socket_is_closed:
            try:
                self.socket.shutdown(2)
                self.socket.close()
                logger.info("Socket closed.")
                self.socket_is_closed = True

            except Exception as e:
                logger.error("Error closing socket. {}".format(traceback))
