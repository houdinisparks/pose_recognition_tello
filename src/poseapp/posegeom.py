from queue import Queue

import math
import numpy as np


class PoseGeom:
    # using coco dataset

    LEFT_SHOULDER = 2
    LEFT_ELBOW = 3
    LEFT_HAND = 4
    RIGHT_SHOULDER = 5
    RIGHT_ELBOW = 6
    RIGHT_HAND = 7

    LIST_OF_JOINTS = [LEFT_SHOULDER, LEFT_ELBOW, LEFT_HAND, RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_HAND]

    # @classmethod
    # def recognise_poses(cls,frame,humans):

    @classmethod
    def angle_btw_2_points(cls, joint_A, joint_B):
        # because the y coordinate increases from to top to bottom, we switch te y
        # x1 y1 are the points to along horizontal axis
        # https://stackoverflow.com/questions/2676719/calculating-the-angle-between-the-line-defined-by-two-points
        angle_rads = math.atan2(joint_B.y - joint_A.y, joint_B.x - joint_A.x)
        angle_rads = -angle_rads
        # if (angle_rads < 0):
        #     angle_rads = abs(angle_rads)
        #
        # else:
        #     angle_rads = 2 * math.pi - angle_rads

        return math.degrees(angle_rads)

    @classmethod
    def distance_btw_2_points(cls, joint_A, joint_B):
        a = np.array((joint_A.x, joint_A.y))
        b = np.array((joint_B.x, joint_B.y))
        return np.linalg.norm(a - b)

    @classmethod
    def is_takeoff(cls, joints):
        # right joints: jointA (shoulder) ->jointB (elbow) -> jointC (hand)
        # left joint: jointD (shoulder) -> jointE (elbow) -> jointF (hand)

        # if (0 < cls.angle_btw_2_points(joints[cls.RIGHT_SHOULDER], joints[cls.RIGHT_ELBOW]) < 90 and
        #         0 < cls.angle_btw_2_points(joints[cls.RIGHT_ELBOW], joints[cls.RIGHT_HAND]) < 90 and
        #         90 < cls.angle_btw_2_points(joints[cls.LEFT_SHOULDER], joints[cls.LEFT_ELBOW]) < 180 and
        #         90 < cls.angle_btw_2_points(joints[cls.LEFT_ELBOW], joints[cls.LEFT_HAND]) < 180):

        if joints.keys() >= {cls.RIGHT_ELBOW, cls.LEFT_ELBOW}:
            if (0 < cls.angle_btw_2_points(joints[cls.RIGHT_SHOULDER], joints[cls.RIGHT_ELBOW]) < 90 and
                    90 < cls.angle_btw_2_points(joints[cls.LEFT_SHOULDER], joints[cls.LEFT_ELBOW]) < 180):
                return True

        return False

    @classmethod
    def is_land(cls, joints):
        # joints: jointA (shoulder) ->jointB (elbow) -> jointC (hand)
        if all(elem in joints.keys() for elem in PoseGeom.LIST_OF_JOINTS):
            if (cls.angle_btw_2_points(joints[cls.RIGHT_SHOULDER], joints[cls.RIGHT_ELBOW]) < 0 and
                    cls.angle_btw_2_points(joints[cls.RIGHT_ELBOW], joints[cls.RIGHT_HAND]) < 0 and
                    cls.angle_btw_2_points(joints[cls.LEFT_SHOULDER], joints[cls.LEFT_ELBOW]) < 0 and
                    cls.angle_btw_2_points(joints[cls.LEFT_ELBOW], joints[cls.LEFT_HAND]) < 0):

                if (cls.distance_btw_2_points(joints[cls.LEFT_HAND], joints[cls.RIGHT_HAND])) < 0.08:
                    return True

        return False

    @classmethod
    def go_right(cls, joints):
        # joints: jointA (shoulder) ->jointB (elbow) -> jointC (hand)
        if joints.keys() >= {cls.RIGHT_ELBOW, cls.RIGHT_SHOULDER, cls.RIGHT_HAND, cls.LEFT_ELBOW, cls.LEFT_SHOULDER}:
            if (abs(cls.angle_btw_2_points(joints[cls.RIGHT_SHOULDER], joints[cls.RIGHT_ELBOW]) < 50) and
                    abs(cls.angle_btw_2_points(joints[cls.RIGHT_ELBOW], joints[cls.RIGHT_HAND])) < 50 and
                    -160 < cls.angle_btw_2_points(joints[cls.LEFT_SHOULDER], joints[cls.LEFT_ELBOW]) < 0):
                return True

        return False

    @classmethod
    def go_left(cls, joints):
        if joints.keys() >= {cls.RIGHT_SHOULDER, cls.LEFT_ELBOW, cls.LEFT_SHOULDER,cls.LEFT_HAND, cls.RIGHT_ELBOW}:
            if (abs(cls.angle_btw_2_points(joints[cls.LEFT_SHOULDER], joints[cls.LEFT_ELBOW])) > 145 and
                    abs(cls.angle_btw_2_points(joints[cls.LEFT_ELBOW], joints[cls.LEFT_HAND])) > 145 and
                    cls.angle_btw_2_points(joints[cls.RIGHT_SHOULDER], joints[cls.RIGHT_ELBOW]) < -25):
                return True

        return False

    @classmethod
    def flip(cls, joints):
        if all(elem in joints.keys() for elem in PoseGeom.LIST_OF_JOINTS):
            if (abs(cls.angle_btw_2_points(joints[cls.LEFT_ELBOW], joints[cls.LEFT_HAND])) < 15 and
                    abs(cls.angle_btw_2_points(joints[cls.RIGHT_ELBOW], joints[cls.RIGHT_HAND])) > 135):
                return True

        return False
