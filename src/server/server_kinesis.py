# from amazon_kclpy import kcl
# from tf_pose.estimator import TfPoseEstimator
# from tf_pose.networks import get_graph_path, model_wh
# import tensorflow as tf
#
# # configure the kinesis settings
# # awskcl_helper.py --print_command \
# #     --java <path-to-java> --properties samples/sample.properties
# from src.server.kinesisprocessor import KinesisProcessor
#
# # n_workers = int(input("Number of workers for thread pool? "))
# n_workers = 2
# estimator = TfPoseEstimator(get_graph_path("mobilenet_thin"), target_size=(432, 368), tf_config=tf.ConfigProto(log_device_placement=True))
# w, h = model_wh("432x368")
#
# if __name__ == "__main__":
#     print("Server initializing...")
#     kcl_process = kcl.KCLProcess(KinesisProcessor(tf_op=estimator,
#                                                   w=w, h=h,n_workers = n_workers,n_shards=2,
#                                                   result_stream="poserec_results"))
#     kcl_process.run()
