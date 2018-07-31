# 1,2,   1,5,   2,3,   3,4,   5,6,   6,7,   1,8,   8,9,   9,10,  1,11,  11,12, 12,13,  1,0,   0,14, 14,16,  0,15, 15,17
import logging

import math

logger = logging.getLogger(__name__)

class Pose_RNN:
    timesteps = 5  # 5 frames per sample
    max_pose_count = 10  # no. of maximum poses
    max_pose_score_pair = 36  # 17 pairs * 2 person for pose scores + 2 padding
    pose_names = []

    # PREDEFINED LABELS. CHANGE THIS IF USING DIFFERENT LABELS.
    pose_labels = {
        0: "standing",
        1: "sitting"
    }

    pose_sample_type = []  # stores the max pose score pair * timesteps. total len == 180
    coco_pose_pairs = [1, 2, 1, 5, 2, 3, 3, 4, 5, 6, 6, 7, 1, 8, 8, 9, 9, 10, 1, 11, 11, 12, 12, 13, 1, 0, 0, 14, 14,
                       16, 0, 15, 15, 17]  # pairs based on coco dataset.)
    #
    pose_samples_labels = []  # total len = max pose count. stores the names of poses.
    pose_sample = []  # holds the training sample. len = 180
    pose_samples = []

    @classmethod
    def generate_samples_from_keypoints(cls, keypoints, frame_count_in_sample,
                                        label, distance="l2"):

        if(len(keypoints) < 36):
            logger.error("Keypoints only have {} which is <  36, please use a new image to generate the keypoints again.".format(len(keypoints)))
            raise RuntimeError("Keypoints less than 36, please use a new image to generate the keypoints again.")

        pair = 0
        while pair < len(cls.coco_pose_pairs):

            # obtain keypoint index per pair
            idx_1 = cls.coco_pose_pairs[pair]
            idx_2 = cls.coco_pose_pairs[pair + 1]

            joint_1 = 0  # 0 is neck keypoint
            joint_2 = cls.coco_pose_pairs[pair + 1]

            if distance == "l2":
                # calculate euclidian distance
                cls.pose_sample[frame_count_in_sample * len(cls.coco_pose_pairs) + pair] = \
                    cls.compute_l2_dist(keypoints, joint_1, joint_2)

            elif distance == "cosine":
                cls.pose_sample[frame_count_in_sample * len(cls.coco_pose_pairs) + pair] = \
                    cls.compute_cosine_dist(keypoints, joint_1, joint_2)
            else:

                raise RuntimeError("Error!")

            pair += 2

        #todo: write sample image to file.

        if frame_count_in_sample == cls.timesteps - 1:
            cls.pose_samples.append(cls.pose_sample)
            cls.pose_samples_labels.append(label)

            cls.pose_sample = []

            pass

    @classmethod
    def write_samples_to_file(cls, train_dir):

        if len(cls.pose_samples) % 5 != 0:
            raise RuntimeError("Please capture an additional {} frames. You need 5 frames for each sample.".format(len(cls.pose_samples) % 5))

        try:
            with open(train_dir + "/pose_samples_raw.txt", "w") as f:
                for line in cls.pose_samples:
                    f.write(",".join(map(str, [str(i) for i in line])))
                    f.write("\n")

            with open(train_dir + "/pose_labels_raw.txt") as f:
                for line in cls.pose_samples:
                    f.write(",".join(map(str, [str(i) for i in line])))
                    f.write("\n")

        except:
            raise RuntimeError("Writing to file error occurred.")

    # reference
    # https://github.com/srianant/computer_vision/blob/ec59d530806020774e1913e58717f4fee0067467/openpose/src/openpose/user_code/pose_model.cpp
    @classmethod
    def get_pose_predictions(cls):
        pass

    @classmethod
    def compute_l2_dist(cls, keypoints, joint_1, joint_2):

        joint_1_x = keypoints[joint_1 * 3]
        joint_1_y = keypoints[joint_2 * 3 + 1]

        joint_2_x = keypoints[joint_2 * 3]
        joint_2_y = keypoints[joint_2 * 3 + 1]

        return math.sqrt((joint_1_x - joint_2_x) ** 2 +
                         (joint_1_y - joint_2_y) ** 2)

    @classmethod
    def compute_cosine_dist(cls, keypoints, joint_1, joint_2):

        joint_1_x = keypoints[joint_1 * 3]
        joint_1_y = keypoints[joint_2 * 3 + 1]

        joint_2_x = keypoints[joint_2 * 3]
        joint_2_y = keypoints[joint_2 * 3 + 1]

        numerator = (joint_1_x * joint_2_x) + (joint_1_y * joint_2_y)
        denom = (math.sqrt(abs(joint_2_x ** 2) + abs(joint_2_y ** 2))) * \
                (math.sqrt(abs(joint_1_x ** 2) + abs(joint_1_y ** 2)))

        return 1 - (numerator / denom)
