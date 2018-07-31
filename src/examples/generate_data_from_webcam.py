# reference: https://github.com/srianant/computer_vision/blob/ec59d530806020774e1913e58717f4fee0067467/openpose/examples/user_code/openpose_recognition.cpp
#
#todo: write a program that generates data.
# either we can use tf-examples-estimator, and then implement te renderPose ourselves.

# only for one human
# the keypoints here has been normalized.
# try training keras with the normalised keypoints.
import argparse
import copy
import json
import logging

import datetime
import time

import cv2
from tf_pose import common
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import get_graph_path, model_wh

from src.pose_classification.pose_rnn import Pose_RNN

logger = logging.getLogger(__name__)


def generate_keypoints(npimg,humans):
    if len(humans) > 1:
        logging.warning("Will only generated keypoints for the human with the highest score.")

    human = humans[0] # only take the top human
    keypoints = []
    for i in range(common.CocoPart.Background.value):
        if i not in human.body_parts.keys():
            continue
        keypoints.append(human.body_parts[i].x)
        keypoints.append(human.body_parts[i].y)

        # body_part = human.body_parts[i] #
        # center = (int(body_part.x * image_w + 0.5), int(body_part.y * image_h + 0.5))
        # centers[i] = center
    return keypoints



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
    args = parser.parse_args()

    #################################
    # DECLARE VARIABLES #############
    #################################
    frame_count_in_sample = 0
    fps_time = 0

    ###########################
    # START CAMERA ############
    ###########################
    logger.debug('initialization %s : %s' % (args.model, get_graph_path(args.model)))
    w, h = model_wh(args.resize)
    if w > 0 and h > 0:
        e = TfPoseEstimator(get_graph_path(args.model), target_size=(w, h))
    else:
        e = TfPoseEstimator(get_graph_path(args.model), target_size=(432, 368))
    logger.debug('cam read+')
    cam = cv2.VideoCapture(args.camera)
    ret_val, image = cam.read()
    logger.info('cam image=%dx%d' % (image.shape[1], image.shape[0]))
    while True:
        ####################################################
        # START CAMERA STREAM AND DRAW THE SKELETONS #######
        ####################################################
        ret_val, image = cam.read()
        raw_image = copy.deepcopy(image)

        logger.debug('image process+')
        humans = e.inference(image, resize_to_default=(w > 0 and h > 0), upsample_size=args.resize_out_ratio)

        logger.debug('postprocess+')
        image = TfPoseEstimator.draw_humans(image, humans, imgcopy=False)

        logger.debug('show+')
        cv2.putText(image,
                    "FPS: %f" % (1.0 / (time.time() - fps_time)),
                    (10, 10),  cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 2)
        cv2.imshow('tf-pose-estimation result', image)
        fps_time = time.time()

        #######################################################
        # PROCESSING KEY INPUTS ###############################
        #######################################################
        # http://www.asciitable.com/ for key codes

        if cv2.waitKey(1) == 99: # key 'c to capture pose image
            cv2.imwrite("../../train_data/images/" + datetime.datetime.now().strftime('%m-%d_%H-%M-%S') + ".png", raw_image)

        if cv2.waitKey(1) == 103: # key 'g' to generate samples for training:
            label = input("Please enter the pose number you will like to generate samples for:"
                          "{}\n\n Pose number: ".format(json.dumps(Pose_RNN.pose_labels, indent=4)))

            cv2.imshow("pose image", image)

            success = input("Is pose okay? (y/n)")

            if success == "y":
                try:
                    keypoints = generate_keypoints(image, humans)
                    Pose_RNN.generate_samples_from_keypoints(keypoints, frame_count_in_sample,
                                                             label)

                    if frame_count_in_sample == 5:
                        frame_count_in_sample = 0
                    else:
                        frame_count_in_sample += 1

                except RuntimeError as ex:
                    logger.error(str(ex))

        if cv2.waitKey(1) == 116: #key 'o' to output train samples to .txt
            Pose_RNN.write_samples_to_file("train_data")

        if cv2.waitKey(1) == 27:
            break

        logger.debug('finished+')

    cv2.destroyAllWindows()

