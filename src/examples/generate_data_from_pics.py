# reference: https://github.com/srianant/computer_vision/blob/ec59d530806020774e1913e58717f4fee0067467/openpose/examples/user_code/openpose_recognition.cpp
#
# todo: write a program that generates data.
# either we can use tf-examples-estimator, and then implement te renderPose ourselves.

# only for one human
# the keypoints here has been normalized.
# try training keras with the normalised keypoints.
import argparse
import json
import logging
import numpy as np

import os
import time

import cv2
from tf_pose import common
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import get_graph_path, model_wh

from src.pose_classification.pose_rnn import Pose_RNN

logger = logging.getLogger(__name__)


def generate_keypoints(npimg, humans):
    if len(humans) > 1:
        logging.warning("Will only generated keypoints for the human with the highest score.")

    human = humans[0]  # only take the top human
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
    parser.add_argument('--image', type=str, default='train_data/images')

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
    w, h = model_wh(args.resize)
    if w == 0 or h == 0:
        e = TfPoseEstimator(get_graph_path(args.model), target_size=(432, 368))
    else:
        e = TfPoseEstimator(get_graph_path(args.model), target_size=(w, h))

    # estimate human poses from a training images !
    imagevstack_count = 0
    list_of_images = np.array([[]])
    imagehstack_count = 0
    imagehstack = np.array([])
    train_data_file_path = "../../{}/".format(args.image)
    for image_file in os.listdir(train_data_file_path):
        image = common.read_imgfile(train_data_file_path + "/" + image_file, None, None)
        if image is None:
            logger.error('Image can not be read, path=%s' % image_file)
            continue

        t = time.time()
        humans = e.inference(image, resize_to_default=(w > 0 and h > 0), upsample_size=args.resize_out_ratio)
        elapsed = time.time() - t

        logger.info('inference image: %s in %.4f seconds.' % (args.image, elapsed))
        keypoints = generate_keypoints(image, humans)
        image = TfPoseEstimator.draw_humans(image, humans, imgcopy=False)

        # list_of_images = np.hstack(list_of_images[imagevstack_count], image)

    while True:
        cv2.imshow("training images" , image)
        # imagehstack_count += 1
        # if imagehstack_count > 7:
        #     list_of_images = np.vstack(list_of_images, imagehstack)
        #     imagehstack = []
        #     imagevstack_count += 1
        #     imagehstack_count = 0

        if cv2.waitKey(1) == 103:  # key 'g' to generate 1 sample for training:
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

        if cv2.waitKey(1) == 116:  # key 'o' to output train samples to .txt
            Pose_RNN.write_samples_to_file("train_data")

        if cv2.waitKey(1) == 27:
            break

        logger.debug('finished+')

    cv2.destroyAllWindows()
