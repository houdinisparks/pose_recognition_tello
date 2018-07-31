import argparse
import logging

import os
import time

import cv2
from tf_pose import common
from tf_pose.estimator import TfPoseEstimator
from tf_pose.networks import model_wh, get_graph_path

from src.poseapp.posegeom import PoseGeom

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def translate_to_actual_dims(image_w, image_h, normalized_pixels_x, normalized_pixels_y):
    x, y = (int( normalized_pixels_x * image_w + 0.5), int(normalized_pixels_y * image_h + 0.5))
    return (x + 15, y)


fontsize = 0.7
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
    # imagevstack_count = 0
    # list_of_images = np.array([[]])
    # imagehstack_count = 0
    # imagehstack = np.array([])
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
        if len(humans) > 0:
            joint_list = humans[
                0].body_parts  # dict: {0: BodyPart:0-(0.49, 0.22) score=0.86, 1: BodyPart:1-(0.49, 0.34) score=0.79
        else:
            logger.info("no humans detected in image path={}".format(image_file))
            continue
        image = TfPoseEstimator.draw_humans(image, humans, imgcopy=False)

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

    # list_of_images = np.hstack(list_of_images[imagevstack_count], image)
    print("joint_2: {0}\tjoint_3: {1}\tangle: {2}\n"
          "joint_3: {1}\tjoint_4: {3}\tangle: {4}".format(joint_list[PoseGeom.LEFT_SHOULDER],
                                                          joint_list[PoseGeom.LEFT_ELBOW],
                                                          "%0.3f" % angle_2_3,
                                                          joint_list[PoseGeom.LEFT_HAND],
                                                          "%0.3f" % angle_3_4))

    while True:
        cv2.imshow("training images", image)

        if cv2.waitKey(1) == 27:
            break

        logger.debug('finished+')

cv2.destroyAllWindows()
