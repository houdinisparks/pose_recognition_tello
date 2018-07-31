import argparse
import logging

import pickle
import socket

import struct
import threading
import traceback
from queue import Queue

import time

import cv2
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import model_wh, get_graph_path

from src.poseapp.posegeom import PoseGeom
from src.utilities.tello import Tello

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Declare global variables
tello = None
processed_fifo = Queue()
post_processed_fifo = Queue()
delay_time = 200  # 1000/delaytime = fps


def translate_to_actual_dims(w, h, normalized_pixels_x, normalized_pixels_y):
    x, y = (int(round(w * normalized_pixels_x + 0.5)), int(round(h * normalized_pixels_y)))
    return (x + 15, y)



def recv_thread(conn):
    global tello
    global processed_fifo
    global post_processed_fifo
    print("Starting receiving thread")
    data = b''
    payload_size = struct.calcsize("<L")
    fps_time = 0
    pose = "None"
    t = threading.currentThread()

    while True and getattr(t, "do_run", True):
        try:

            while len(data) < payload_size:
                data += conn.recv(8192)
                #  print("Payload data received: {}\n".format(data))
            packed_msg_size = data[:payload_size]
            human_payload_size = struct.unpack("<L", packed_msg_size)[0]  # of bytes in frame.

            # Get the human data
            data = data[payload_size:]
            while len(data) < human_payload_size:
                data += conn.recv(8192)
        except:
            print("Exception occurred: {}".format(traceback.format_exc()))
            with processed_fifo.mutex:
                processed_fifo.queue.clear()
            conn.close()
            break

        human_data = data[:human_payload_size]
        data = data[human_payload_size:]

        # Convert the frame and human data back to its original form.
        humans = pickle.loads(human_data)
        frame = processed_fifo.get(block=True)
        frame = TfPoseEstimator.draw_humans(frame, humans)

        if len(humans) > 0:
            frame = recognise_poses(frame, humans)

        cv2.putText(frame,
                    "FPS: %f" % (1.0 / (time.time() - fps_time)),
                    (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 2)

        print("Frames processed per second: %f" % (1.0 / (time.time() - fps_time)))
        fps_time = time.time()

        post_processed_fifo.put(frame)

        # cv2.imshow('tf-pose-estimation result from server', frame)

        # if cv2.waitKey(1) == 27:
        #     break

        logger.debug('finished+')

    conn.shutdown(2)
    conn.close()


def recognise_poses(image, humans):
    joint_list = humans[0].body_parts
    pose = "None"
    fontsize = 0.5

    # todo instantiate the tello and fly them here

    if all(elem in joint_list.keys() for elem in PoseGeom.LIST_OF_JOINTS):
        image_h, image_w = image.shape[:2]

        # calculate angle between left shoulder and left elbow
        angle_2_3 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_SHOULDER],
                                                joint_list[PoseGeom.LEFT_ELBOW])

        cv2.putText(image, "angle: %0.2f" % angle_2_3,
                    translate_to_actual_dims(image_w, image_h, joint_list[PoseGeom.LEFT_SHOULDER].x - 0.27,
                                             joint_list[PoseGeom.RIGHT_SHOULDER].y),
                    cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

        # calculate angle between left elbow and left elbow
        angle_3_4 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_ELBOW],
                                                joint_list[PoseGeom.LEFT_HAND])

        cv2.putText(image, "angle: %0.2f" % angle_3_4,
                    translate_to_actual_dims(image_w, image_h, joint_list[PoseGeom.LEFT_ELBOW].x - 0.27,
                                             joint_list[PoseGeom.LEFT_ELBOW].y),
                    cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

        angle_5_6 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_SHOULDER],
                                                joint_list[PoseGeom.RIGHT_ELBOW])
        cv2.putText(image, "angle: %0.2f" % angle_5_6,
                    translate_to_actual_dims(image_w, image_h, joint_list[PoseGeom.RIGHT_SHOULDER].x,
                                             joint_list[PoseGeom.RIGHT_SHOULDER].y),
                    cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

        angle_6_7 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_ELBOW],
                                                joint_list[PoseGeom.RIGHT_HAND])

        cv2.putText(image, "angle: %0.2f" % angle_6_7,
                    translate_to_actual_dims(image_w, image_h, joint_list[PoseGeom.RIGHT_ELBOW].x,
                                             joint_list[PoseGeom.RIGHT_ELBOW].y),
                    cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

        # calculate the distance between the 2 hands
        distance_4_7 = PoseGeom.distance_btw_2_points(joint_list[PoseGeom.LEFT_HAND],
                                                      joint_list[PoseGeom.RIGHT_HAND])

        cv2.putText(image, "distance: %0.2f" % distance_4_7,
                    translate_to_actual_dims(image_w, image_h, joint_list[PoseGeom.RIGHT_HAND].x,
                                             joint_list[PoseGeom.RIGHT_HAND].y),
                    cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)

        try:
            if PoseGeom.is_takeoff(joint_list):

                pose = "takeoff"
                tello.takeoff()

            elif PoseGeom.is_land(joint_list):

                pose = "land"
                tello.land()

            elif PoseGeom.go_right(joint_list):

                pose = "right"
                tello.move_right(0.2)

            elif PoseGeom.go_left(joint_list):

                pose = "left"
                tello.move_left(0.2)

            else:
                pose = "None"
        except:
            print("Exception occured: {}".format(traceback.format_exc()))

        cv2.putText(image, "pose: {0}".format(pose),
                    (int(round(image_w / 3)), int(round((image_h - 20)))), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                    (0, 255, 0), 2)

    return image

# processing is done here. when remote-server is available, it is sent to server instead.
def run_processing(camera=0, resize='0x0', resize_out_ratio=4.0, model="mobilenet_thin", show_process=False,
                   remote_server=''):
    #################################
    # DECLARE VARIABLES #############
    #################################
    frames_sent_per_sec = time.time()
    fps_time = 0
    pose = "None"
    logger.debug('initialization %s : %s' % (model, get_graph_path(model)))
    w, h = model_wh(resize)
    t = threading.currentThread()

    global tello

    try:
        tello = Tello("192.168.10.3", 8888, imperial=False, command_timeout=0.3)

    except Exception as e:
        print("Exception Occurred: {}".format(traceback.format_exc()))
        if isinstance(tello, Tello):
            del tello

    if remote_server != '':
        # 2 threads in total. 1 for listening 1 for receiving

        clientsocket = None
        while clientsocket is None:
            try:
                serverip = remote_server.split(":")[0]
                port = remote_server.split(":")[1]
                clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                clientsocket.connect((serverip, int(port)))
                print("Connected to {}:{}".format(serverip, port))

                time.sleep(2)

            except socket.error:
                raise RuntimeError("Connection error with server, trying again...")

        try:
            # start receiving thread
            th = threading.Thread(target=recv_thread, args=(clientsocket,))
            th.do_run = True
            th.daemon = True # main thread and still exit even if this thread is running.
            th.start()

        except Exception:
            raise RuntimeError("Error starting thread, trying again...")

    else:
        if w > 0 and h > 0:
            e = TfPoseEstimator(get_graph_path(model), target_size=(w, h))
        else:
            e = TfPoseEstimator(get_graph_path(model), target_size=(432, 368))

    ###########################
    # START CAMERA ############
    ###########################

    cam = cv2.VideoCapture(camera)
    # cam.set(cv2.CAP_PROP_FPS, 3)
    ret_val, image = cam.read()
    logger.info('cam image=%dx%d' % (image.shape[1], image.shape[0]))
    while True and getattr(t, "do_run", True):
        ####################################################
        # START CAMERA STREAM AND DRAW THE SKELETONS #######
        ####################################################
        ret_val, image = cam.read()
        image = cv2.flip(image, 1)

        # raw_image = copy.deepcopy(image)
        if remote_server != '':

            # start sending frame
            try:
                data = pickle.dumps(image)
                clientsocket.sendall(struct.pack("<L", len(data)) + data)
                processed_fifo.put(image, block=True)
                print("frames sent per second %s" % (1.0 / (time.time() - frames_sent_per_sec)))

            except ZeroDivisionError:
                continue

            except Exception as e:
                print("Exception occurred: {}".format(traceback.format_exc()))
                clientsocket.shutdown(2)
                clientsocket.close()
                with processed_fifo.mutex:
                    processed_fifo.queue.clear()
                break

            # delay_time = 1000 / (1.0 / (time.time() - frames_sent_per_sec))  # 1000/delaytime = fps
            frames_sent_per_sec = time.time()

            # cv2.waitKey(int(math.ceil(delay_time)))
            cv2.waitKey(delay_time)

            continue

        # todo: send image to cpu instance on aws
        logger.debug('image process+')
        humans = e.inference(image, resize_to_default=(w > 0 and h > 0), upsample_size=resize_out_ratio)

        logger.debug('postprocess+')
        image = TfPoseEstimator.draw_humans(image, humans, imgcopy=False)

        # image = cv2.resize(image , (2*w,2*h),
        #                    interpolation = cv2.INTER_LINEAR)

        if len(humans) > 0:
            recognise_poses(image, humans)

        cv2.putText(image,
                    "FPS: %f" % (1.0 / (time.time() - fps_time)),
                    (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 2)

        fps_time = time.time()

        cv2.imshow('tf-pose-estimation result', image)

        if cv2.waitKey(1) == 115:
            # start the recognition
            pass

        if cv2.waitKey(1) == 27:
            break

        logger.debug('finished+')

    # exit receiving thread
    if (th.do_run):
        th.do_run = False
        th.join()
    with processed_fifo.mutex:
        processed_fifo.queue.clear()

    clientsocket.shutdown(2)
    clientsocket.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    #########################
    # ARGUMENT PARSER #######
    #########################
    parser = argparse.ArgumentParser(description='tf-pose-estimation training samples generator')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--resize', type=str, default='0x0',
                        help='if provided, resize images before they are processed. default=0x0, Recommends : 432x368 or 656x368 or 1312x736 ')
    parser.add_argument('--resize-out-ratio', type=float, default=4.0,
                        help='if provided, resize heatmaps before they are post-processed. default=1.0')
    parser.add_argument('--model', type=str, default='mobilenet_thin', help='cmu / mobilenet_thin')
    parser.add_argument('--show-process', type=bool, default=False,
                        help='for debug purpose, if enabled, speed for inference is dropped.')
    parser.add_argument('--remote-server', type=str, default='',
                        help='sent to remote server for processing')
    args = parser.parse_args()

    run_processing(args.camera, args.resize, args.resize_out_ratio, args.model, args.show_process, args.remote_server)

# # Get length of the frame size (frame_payload_size)
# while len(data) < payload_size:
#     data += conn.recv(65535)
#     print("Payload data received: {}\n".format(data))
# packed_msg_size = data[:payload_size]
# frame_payload_size = struct.unpack("<L", packed_msg_size)[0]  # of bytes in frame.

# Get length of the human data size (human_payload_size)
# data = data[payload_size:]


# # Get the frame data
# data = data[payload_size:]
# while len(data) < frame_payload_size:
#     data += conn.recv(65535)
# frame_data = data[:frame_payload_size]
