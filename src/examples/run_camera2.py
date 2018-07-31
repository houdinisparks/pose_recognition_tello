import argparse
import threading
import traceback

import cv2
from tf_pose.estimator import TfPoseEstimator

from src.poseapp.poseapp_sockets import PoseAppWSockets
from src.utilities.framesocketstream import FrameSocketStream
from src.utilities.tello import Tello


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

    poseapp = PoseAppWSockets(args.camera, args.resize, args.resize_out_ratio, args.model, args.show_process, args.remote_server)
    poseapp.start() # press esc to exit




