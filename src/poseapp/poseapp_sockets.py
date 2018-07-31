import logging
import threading
import traceback
from queue import Queue

import cv2
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import get_graph_path, model_wh

from src.poseapp.posegeom import PoseGeom
from src.utilities.framesocketstream import FrameSocketStream
from src.utilities.tello import Tello
import time
import tensorflow as tf

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PoseAppWSockets():

    def __init__(self, camera=0, resize='0x0', resize_out_ratio=4.0, model="mobilenet_thin", show_process=False,
                 remote_server='', delay_time=500, tello=None):

        self.delay_time = delay_time
        self.remote_server = remote_server
        self.show_process = show_process
        self.model = model
        self.resize = resize
        self.resize_out_ratio = resize_out_ratio
        self.camera = camera

        self.tello_connected = False
        self._frame_sent_queue = Queue()
        self.frame_processed_queue = Queue()
        self.tello = tello
        self.socket = None
        self.start_th = None
        self.sent_fps = time.time()
        self.received_fps = time.time()
        self.fps_time = time.time()

    def init_tello_connection(self):
        self.tello.init_connection()
        # try:
        #     self.tello = Tello("192.168.10.3", 8888, imperial=False, command_timeout=0.3)
        #     self.tello_connected = True
        #
        # except Exception as e:
        #     print("Exception Occurred: {}".format(traceback.format_exc()))
        #     self.tello_connected = False
        #     if isinstance(self.tello, Tello):
        #         del self.tello
        #     time.sleep(2)

    def start(self, remote_server_ip=None):
        """
        Start the sending thread to send frames to server. Sockets is handled by FrameSocketStream.
        :param remote_server_ip:
        :return:
        """
        self.start_th_signal = threading.Event()
        self.start_th = threading.Thread(target=self._th_start)
        if remote_server_ip is not None:
            self.remote_server = remote_server_ip

        # self.start_th.do_run = True
        # self.start_th.daemon = True
        self.start_th.start()

    def stop(self):
        try:
            if not self.start_th_signal.is_set():
                self.start_th_signal.set()
                self.start_th.join()

            # clear the queues
            with self.frame_processed_queue.mutex:
                self.frame_processed_queue.queue.clear()

            with self._frame_sent_queue.mutex:
                self._frame_sent_queue.queue.clear()

            # reset all variables.
            self.sent_fps = time.time()
            self.received_fps = time.time()
            return True

        except Exception as e:
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def translate_to_actual_dims(w, h, normalized_pixels_x, normalized_pixels_y):
        x, y = (int(round(w * normalized_pixels_x + 0.5)), int(round(h * normalized_pixels_y)))
        return x + 15, y

    def draw_frame(self, frame, pose):

        logger.debug("pose: {}".format(pose))
        self.move_tello(pose)

        try:
            cv2.putText(frame,
                        "FPS: %f" % (1.0 / (time.time() - self.received_fps)),
                        (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 0), 2)
            # logger.info("fps received %s" % (1.0 / (time.time() - self.received_fps)))

        except ZeroDivisionError:
            logger.error("FPS division error")

        self.received_fps = time.time()
        self.frame_processed_queue.put(frame)

    def draw_humans(self, humans):

        frame = self._frame_sent_queue.get()

        # this portion does not cause the bottleneck
        frame = TfPoseEstimator.draw_humans(frame, humans)
        # if len(humans) > 0:
        # frame = self.identify_body_gestures(frame, humans)

        try:
            cv2.putText(frame,
                        "FPS: %f" % (1.0 / (time.time() - self.received_fps)),
                        (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 0), 2)
            # logger.info("fps received %s" % (1.0 / (time.time() - self.received_fps)))

        except ZeroDivisionError:
            logger.error("FPS division error")

        self.received_fps = time.time()
        self.frame_processed_queue.put(frame)

    @staticmethod
    def identify_body_gestures(frame, human):
        joint_list = human.body_parts
        pose = "none"
        fontsize = 0.5

        try:
            if all(elem in joint_list.keys() for elem in PoseGeom.LIST_OF_JOINTS):
                image_h, image_w = frame.shape[:2]

                # calculate angle between left shoulder and left elbow
                angle_2_3 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_SHOULDER],
                                                        joint_list[PoseGeom.LEFT_ELBOW])

                cv2.putText(frame, "angle: %0.2f" % angle_2_3,
                            PoseAppWSockets.translate_to_actual_dims(image_w, image_h,
                                                                     joint_list[PoseGeom.LEFT_SHOULDER].x - 0.27,
                                                                     joint_list[PoseGeom.RIGHT_SHOULDER].y),
                            cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

                # calculate angle between left elbow and left elbow
                angle_3_4 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_ELBOW],
                                                        joint_list[PoseGeom.LEFT_HAND])

                cv2.putText(frame, "angle: %0.2f" % angle_3_4,
                            PoseAppWSockets.translate_to_actual_dims(image_w, image_h,
                                                                     joint_list[PoseGeom.LEFT_ELBOW].x - 0.27,
                                                                     joint_list[PoseGeom.LEFT_ELBOW].y),
                            cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

                angle_5_6 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_SHOULDER],
                                                        joint_list[PoseGeom.RIGHT_ELBOW])
                cv2.putText(frame, "angle: %0.2f" % angle_5_6,
                            PoseAppWSockets.translate_to_actual_dims(image_w, image_h,
                                                                     joint_list[PoseGeom.RIGHT_SHOULDER].x,
                                                                     joint_list[PoseGeom.RIGHT_SHOULDER].y),
                            cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

                angle_6_7 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_ELBOW],
                                                        joint_list[PoseGeom.RIGHT_HAND])

                cv2.putText(frame, "angle: %0.2f" % angle_6_7,
                            PoseAppWSockets.translate_to_actual_dims(image_w, image_h,
                                                                     joint_list[PoseGeom.RIGHT_ELBOW].x,
                                                                     joint_list[PoseGeom.RIGHT_ELBOW].y),
                            cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

                # calculate the distance between the 2 hands
                distance_4_7 = PoseGeom.distance_btw_2_points(joint_list[PoseGeom.LEFT_HAND],
                                                              joint_list[PoseGeom.RIGHT_HAND])

                cv2.putText(frame, "distance: %0.2f" % distance_4_7,
                            PoseAppWSockets.translate_to_actual_dims(image_w, image_h,
                                                                     joint_list[PoseGeom.RIGHT_HAND].x,
                                                                     joint_list[PoseGeom.RIGHT_HAND].y),
                            cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

                if PoseGeom.is_takeoff(joint_list):
                    pose = "takeoff"

                elif PoseGeom.is_land(joint_list):
                    pose = "land"

                elif PoseGeom.go_right(joint_list):
                    pose = "right"

                elif PoseGeom.go_left(joint_list):
                    pose = "left"

                elif PoseGeom.flip(joint_list):
                    pose = "flip"

                else:
                    pose = "none"

                cv2.putText(frame, "pose: {0}".format(pose),
                            (int(round(image_w / 3)), int(round((image_h - 20)))), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                            (0, 255, 0), 2)

        except Exception as e:
            logger.error(traceback.format_exc())

        return frame, pose

    def move_tello(self, pose):
        try:
            if pose == "takeoff":
                self.tello.takeoff()
            elif pose == "land":
                self.tello.land()
            elif pose == "right":
                self.tello.move_right(0.2)
            elif pose == "left":
                self.tello.move_left(0.2)
            elif pose == "flip":
                self.tello.flip("f")
            else:
                return "none"

        except Exception as e:
            logger.error("tello exp {}".format(traceback.format_exc()))

    def _th_start(self):
        """
        Start the socket connection and stream the footage to the aws server.
        Socket is only exposed in this function.
        :return:
        """

        logger.debug('cam read+')
        cam = cv2.VideoCapture(self.camera)
        ret_val, frame = cam.read()
        logger.debug('initialization %s : %s' % (self.model, get_graph_path(self.model)))
        logger.info('cam image=%dx%d' % (frame.shape[1], frame.shape[0]))
        w, h = model_wh(self.resize)

        if self.remote_server != '':
            try:
                serverip = self.remote_server.split(":")[0]
                port = self.remote_server.split(":")[1]
                socket = FrameSocketStream(serverip, port)
                socket.init_connection()

                # start the receiving thread with the callback function to process
                # the result
                socket.start_recv_thread(recv_callback=self.draw_frame)
            except RuntimeError:
                logger.error("Problem connecting to server. Please try again")
                return

        else:
            if w > 0 and h > 0:
                e = TfPoseEstimator(get_graph_path(self.model), target_size=(w, h),
                                    tf_config=tf.ConfigProto(log_device_placement=True))
            else:
                e = TfPoseEstimator(get_graph_path(self.model), target_size=(432, 368),
                                    tf_config=tf.ConfigProto(log_device_placement=True))

        t = threading.currentThread()

        while True and not self.start_th_signal.wait(self.delay_time / 1000):

            ####################################################
            # START CAMERA STREAM AND DRAW THE SKELETONS #######
            ####################################################
            ret_val, frame = cam.read()
            frame = cv2.flip(frame, 1)

            if self.remote_server != '':
                self._frame_sent_queue.put(frame)
                socket.send(frame)

            else:
                logger.debug('image process+')
                humans = e.inference(frame, resize_to_default=(w > 0 and h > 0), upsample_size=self.resize_out_ratio)
                pose = ''

                logger.debug('postprocess+')
                frame = TfPoseEstimator.draw_humans(frame, humans, imgcopy=False)

                # image = cv2.resize(image , (2*w,2*h),
                #                    interpolation = cv2.INTER_LINEAR)

                if len(humans) > 0:
                    humans.sort(key=lambda x: x.score, reverse=True)
                    humans = humans[:1]  # get the human with the highest score
                    frame = TfPoseEstimator.draw_humans(frame, humans)
                    frame, pose = self.identify_body_gestures(frame, humans[0])

                cv2.putText(frame,
                            "FPS: %f" % (1.0 / (time.time() - self.fps_time)),
                            (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 255, 0), 2)

                self.fps_time = time.time()
                cv2.waitKey(self.delay_time)
                cv2.imshow('tf-pose-estimation result', frame)

                if cv2.waitKey(1) == 27:
                    break

                logger.debug('finished+')

            # todo: this sents at a burst of 3 frames every self.delay_time
            # logger.info("fps send %s" % (1.0 / (time.time() - self.sent_fps)))
            self.sent_fps = time.time()
            cv2.waitKey(self.delay_time)
            # cv2.waitKey(1)
            # time.sleep(self.delay_time / 1000)

        if self.remote_server != '':
            logger.info("Cleaning up socket...")
            socket.close_socket()
            del socket

        cam.release()
        cv2.destroyAllWindows()
        logger.info("Camera released.")
