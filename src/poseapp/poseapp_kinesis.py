# import bisect
# import logging
# import random
# import socket
# import threading
# import traceback
# from queue import Queue
#
# import boto3
# import cv2
# import pickle
#
# import math
# from boto.kinesis.exceptions import ProvisionedThroughputExceededException
# from tf_pose.estimator import TfPoseEstimator
# from tf_pose.networks import get_graph_path, model_wh
#
# from src.poseapp.posegeom import PoseGeom
# from src.utilities.framesocketstream import FrameSocketStream
# from src.utilities.tello import Tello
# import time
#
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
#
#
# class PoseAppWKinesis():
#
#     def __init__(self, produce_stream_name, consumer_stream_name, n_shards=1, camera=0, resize='0x0',
#                  resize_out_ratio=4.0,
#                  model="mobilenet_thin", show_process=False,
#                  remote_server='', delay_time=500, tello=None):
#
#         self.consumer_stream_name = consumer_stream_name
#         self.produce_stream_name = produce_stream_name
#         self.delay_time = delay_time
#         self.remote_server = remote_server
#         self.show_process = show_process
#         self.model = model
#         self.resize = resize
#         self.resize_out_ratio = resize_out_ratio
#         self.camera = camera
#
#         self.tello_connected = False
#         self.frame_processed_queue = Queue()
#         self.tello = tello
#         self.kclient = boto3.client("kinesis", region_name='ap-southeast-1')
#         self.start_th = None
#         self.curr_seq_num = 0
#         self.framelist = []
#         self.n_shards = n_shards
#
#         self.sent_fps = time.time()
#         self.received_fps = time.time()
#         self.fps_time = time.time()
#
#     def init_tello_connection(self):
#         self.tello.init_connection()
#
#     def start(self, remote_server_ip=None):
#         """
#         Start the sending thread to send frames to server. Sockets is handled by FrameSocketStream.
#         :param remote_server_ip:
#         :return:
#         """
#         self.start_th_signal = threading.Event()
#         self.start_th = threading.Thread(target=self._th_start)
#         if remote_server_ip is not None:
#             self.remote_server = remote_server_ip
#
#         self.start_th.start()
#
#         # start the consumer thread
#         self.consume_th = threading.Thread(target=self._th_consume)
#         self.consume_th.start()
#
#     def stop(self):
#         try:
#             if not self.start_th_signal.is_set():
#                 self.start_th_signal.set()
#                 self.start_th.join()
#
#             # clear the queues
#             with self.frame_processed_queue.mutex:
#                 self.frame_processed_queue.queue.clear()
#
#             # with self._frame_sent_queue.mutex:
#             #     self._frame_sent_queue.queue.clear()
#
#             # reset all variables.
#             self.sent_fps = time.time()
#             self.received_fps = time.time()
#             return True
#
#         except Exception as e:
#             logger.error(traceback.format_exc())
#             return False
#
#     @staticmethod
#     def translate_to_actual_dims(w, h, normalized_pixels_x, normalized_pixels_y):
#         x, y = (int(round(w * normalized_pixels_x + 0.5)), int(round(h * normalized_pixels_y)))
#         return x + 15, y
#
#     def draw_frame(self, frame, pose):
#
#         logger.info("pose: {}".format(pose))
#         self.move_tello(pose)
#
#         try:
#             cv2.putText(frame,
#                         "FPS: %f" % (1.0 / (time.time() - self.received_fps)),
#                         (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
#                         (0, 255, 0), 2)
#             # logger.info("fps received %s" % (1.0 / (time.time() - self.received_fps)))
#
#         except ZeroDivisionError:
#             logger.error("FPS division error")
#
#         self.received_fps = time.time()
#         self.frame_processed_queue.put(frame)
#
#     def draw_humans(self, humans):
#
#         frame = self._frame_sent_queue.get()
#
#         # this portion does not cause the bottleneck
#         frame = TfPoseEstimator.draw_humans(frame, humans)
#         # if len(humans) > 0:
#         # frame = self.identify_body_gestures(frame, humans)
#
#         try:
#             cv2.putText(frame,
#                         "FPS: %f" % (1.0 / (time.time() - self.received_fps)),
#                         (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
#                         (0, 255, 0), 2)
#             # logger.info("fps received %s" % (1.0 / (time.time() - self.received_fps)))
#
#         except ZeroDivisionError:
#             logger.error("FPS division error")
#
#         self.received_fps = time.time()
#         self.frame_processed_queue.put(frame)
#
#     @staticmethod
#     def identify_body_gestures(frame, human):
#         joint_list = human.body_parts
#         pose = "none"
#         fontsize = 0.5
#
#         try:
#             if all(elem in joint_list.keys() for elem in PoseGeom.LIST_OF_JOINTS):
#                 image_h, image_w = frame.shape[:2]
#
#                 # calculate angle between left shoulder and left elbow
#                 angle_2_3 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_SHOULDER],
#                                                         joint_list[PoseGeom.LEFT_ELBOW])
#
#                 cv2.putText(frame, "angle: %0.2f" % angle_2_3,
#                             PoseAppWKinesis.translate_to_actual_dims(image_w, image_h,
#                                                                      joint_list[PoseGeom.LEFT_SHOULDER].x - 0.27,
#                                                                      joint_list[PoseGeom.RIGHT_SHOULDER].y),
#                             cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)
#
#                 # calculate angle between left elbow and left elbow
#                 angle_3_4 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.LEFT_ELBOW],
#                                                         joint_list[PoseGeom.LEFT_HAND])
#
#                 cv2.putText(frame, "angle: %0.2f" % angle_3_4,
#                             PoseAppWKinesis.translate_to_actual_dims(image_w, image_h,
#                                                                      joint_list[PoseGeom.LEFT_ELBOW].x - 0.27,
#                                                                      joint_list[PoseGeom.LEFT_ELBOW].y),
#                             cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)
#
#                 angle_5_6 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_SHOULDER],
#                                                         joint_list[PoseGeom.RIGHT_ELBOW])
#                 cv2.putText(frame, "angle: %0.2f" % angle_5_6,
#                             PoseAppWKinesis.translate_to_actual_dims(image_w, image_h,
#                                                                      joint_list[PoseGeom.RIGHT_SHOULDER].x,
#                                                                      joint_list[PoseGeom.RIGHT_SHOULDER].y),
#                             cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)
#
#                 angle_6_7 = PoseGeom.angle_btw_2_points(joint_list[PoseGeom.RIGHT_ELBOW],
#                                                         joint_list[PoseGeom.RIGHT_HAND])
#
#                 cv2.putText(frame, "angle: %0.2f" % angle_6_7,
#                             PoseAppWKinesis.translate_to_actual_dims(image_w, image_h,
#                                                                      joint_list[PoseGeom.RIGHT_ELBOW].x,
#                                                                      joint_list[PoseGeom.RIGHT_ELBOW].y),
#                             cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)
#
#                 # calculate the distance between the 2 hands
#                 distance_4_7 = PoseGeom.distance_btw_2_points(joint_list[PoseGeom.LEFT_HAND],
#                                                               joint_list[PoseGeom.RIGHT_HAND])
#
#                 cv2.putText(frame, "distance: %0.2f" % distance_4_7,
#                             PoseAppWKinesis.translate_to_actual_dims(image_w, image_h,
#                                                                      joint_list[PoseGeom.RIGHT_HAND].x,
#                                                                      joint_list[PoseGeom.RIGHT_HAND].y),
#                             cv2.FONT_HERSHEY_SIMPLEX, fontsize, (0, 255, 0), 2)
#
#                 if PoseGeom.is_takeoff(joint_list):
#                     pose = "takeoff"
#
#                 elif PoseGeom.is_land(joint_list):
#                     pose = "land"
#
#                 elif PoseGeom.go_right(joint_list):
#                     pose = "right"
#
#                 elif PoseGeom.go_left(joint_list):
#                     pose = "left"
#
#                 elif PoseGeom.flip_forward(joint_list):
#                     pose = "flip"
#
#                 else:
#                     pose = "none"
#
#                 cv2.putText(frame, "pose: {0}".format(pose),
#                             (int(round(image_w / 3)), int(round((image_h - 20)))), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
#                             (0, 255, 0), 2)
#
#         except Exception as e:
#             logger.error(traceback.format_exc())
#
#         return frame, pose
#
#     def move_tello(self, pose):
#
#         try:
#             if pose == "takeoff":
#                 self.tello.takeoff()
#             elif pose == "land":
#                 self.tello.land()
#             elif pose == "right":
#                 self.tello.move_right(0.2)
#             elif pose == "left":
#                 self.tello.move_left(0.2)
#             elif pose == "flip":
#                 self.tello.flip_forward("f")
#             else:
#                 return "none"
#
#         except Exception as e:
#             logger.error("tello exp {}".format(traceback.format_exc()))
#
#     def _th_start(self):
#         """
#         Start the socket connection to server and stream the frames to a kinesis data stream.
#         Socket is only exposed in this function.
#         :return:
#         """
#
#         logger.debug('cam read+')
#         cam = cv2.VideoCapture(self.camera)
#         ret_val, frame = cam.read()
#         logger.debug('initialization %s : %s' % (self.model, get_graph_path(self.model)))
#         logger.info('cam image=%dx%d' % (frame.shape[1], frame.shape[0]))
#         w, h = model_wh(self.resize)
#
#         if not self.remote_server != '':
#             if w > 0 and h > 0:
#                 e = TfPoseEstimator(get_graph_path(self.model), target_size=(w, h))
#             else:
#                 e = TfPoseEstimator(get_graph_path(self.model), target_size=(432, 368))
#
#         t = threading.currentThread()
#
#         while True and not self.start_th_signal.wait(self.delay_time / 1000):
#
#             ####################################################
#             # START CAMERA STREAM AND DRAW THE SKELETONS #######
#             ####################################################
#             ret_val, frame = cam.read()
#             frame = cv2.flip(frame, 1)
#
#             if self.remote_server != '':
#
#                 # put data in kinesis stream
#                 package = {
#                     'frame_no': self.curr_seq_num,
#                     'frame': frame
#                 }
#                 partition_key = random.randint(1, self.n_shards)
#                 try:
#                     self.kclient.put_record(
#                         StreamName=self.produce_stream_name,
#                         Data=pickle.dump(package),
#                         PartitionKey=str(partition_key)
#                     )
#                     logger.debug("sent raw frame to part key {}".format(partition_key))
#
#
#                 except Exception as e:
#                     logger.debug(str(e))
#
#             else:
#                 logger.debug('image process+')
#                 humans = e.inference(frame, resize_to_default=(w > 0 and h > 0), upsample_size=self.resize_out_ratio)
#                 pose = ''
#
#                 logger.debug('postprocess+')
#                 frame = TfPoseEstimator.draw_humans(frame, humans, imgcopy=False)
#
#                 # image = cv2.resize(image , (2*w,2*h),
#                 #                    interpolation = cv2.INTER_LINEAR)
#
#                 if len(humans) > 0:
#                     humans.sort(key=lambda x: x.score, reverse=True)
#                     humans = humans[:1]  # get the human with the highest score
#                     frame = TfPoseEstimator.draw_humans(frame, humans)
#                     frame, pose = self.identify_body_gestures(frame, humans[0])
#
#                 cv2.putText(frame,
#                             "FPS: %f" % (1.0 / (time.time() - self.fps_time)),
#                             (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
#                             (0, 255, 0), 2)
#
#                 self.fps_time = time.time()
#                 cv2.waitKey(self.delay_time)
#                 cv2.imshow('tf-pose-estimation result', frame)
#
#                 if cv2.waitKey(1) == 27:
#                     break
#
#                 logger.debug('finished+')
#
#             # todo: this sents at a burst of 3 frames every self.delay_time
#             # logger.info("fps send %s" % (1.0 / (time.time() - self.sent_fps)))
#             self.sent_fps = time.time()
#             cv2.waitKey(self.delay_time)
#             # cv2.waitKey(1)
#             # time.sleep(self.delay_time / 1000)
#
#         if self.remote_server != '':
#             logger.info("")
#
#         cam.release()
#         cv2.destroyAllWindows()
#         logger.info("Camera released.")
#
#     def _th_consume(self):
#
#         # each shard will start its own thread
#         response = self.kclient.describe_stream(StreamName=self.consumer_stream_name)
#         my_shards = response['StreamDescription']['Shards']
#         my_shard_th = []
#         rlock = threading.RLock()
#         for i in range(len(my_shards)):
#             # tart new shard thread
#             my_shard_id = response['StreamDescription']['Shards'][i]['ShardId']
#             shard_iterator = self.kclient.get_shard_iterator(StreamName=self.consumer_stream_name,
#                                                              ShardId=my_shard_id,
#                                                              ShardIteratorType='LATEST')
#
#             th = threading.Thread(target=self._th_shard, args=(shard_iterator, i, rlock))
#             th.start()
#             my_shard_th.append(th)
#
#         while not self.start_th_signal.is_set():
#             pass
#
#         # this line will be reached one th_signal is set
#         for i in range(len(my_shard_th)):
#             my_shard_th[i].join()
#
#         logger.debug("Closing consumer thread.")
#
#     def _th_shard(self, shard_iterator, shard_idx, rlock):
#         my_shard_iterator = shard_iterator['ShardIterator']
#         record_response = self.kclient.get_records(ShardIterator=my_shard_iterator,
#                                                    Limit=5)
#
#         while 'NextShardIterator' in record_response and not self.start_th_signal.wait(self.delay_time / 800):
#             try:
#                 record_response = self.kclient.get_records(ShardIterator=record_response['NextShardIterator'],
#                                                            Limit=5)
#
#                 if len(record_response['Records']) is 0:
#                     logger.debug("No records in consumer stream.")
#
#                 else:
#                     logger.debug("Retrieved {} records in consumer stream.".format(len(record_response['Records'])))
#                     for record in record_response["Records"]:
#                         frame_package = pickle.loads(record['Data'])
#
#                         # insert frame into ordered list based on frame_no. smallest first.
#                         with rlock:
#                             bisect.insort(frame_package, self.framelist)
#
#                         # wait till list has more that 5 frames, then begin showing video
#                         if len(self.framelist) > 5:
#                             self.frame_processed_queue.put(self.framelist[0]['frame'])
#                             self.move_tello(self.framelist[0]['pose'])
#                             self.framelist = self.framelist[1:]
#
#                         # self.frame_processed_queue.put(frame_package["frame"])
#
#                         logger.info("tello pose: {}".format(frame_package['pose']))
#
#             except ProvisionedThroughputExceededException as e:
#                 logger.error("ProvisionedThroughputExceededException")
#
#             except Exception as e:
#                 logger.error(str(e))
#
#         while len(record_response['Records']) is not 0:
#             record_response = self.kclient.get_records(ShardIterator=record_response['NextShardIterator'],
#                                                        Limit=5)
#
# # while True and not self.start_th_signal.is_set():
# #     for data in self.kconsumer:
# #         frame, pose = pickle.loads(data)
# #         self.draw_frame(frame, pose)
#
#
# # insert into a sorted queue
