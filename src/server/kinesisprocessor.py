import concurrent
import logging
import random
import threading
import traceback
from concurrent import futures

import pickle
from queue import Queue, Empty

import boto3
import sys
from amazon_kclpy import kcl
from amazon_kclpy.v2 import processor
import time
from tf_pose.estimator import TfPoseEstimator

# always running
from src.poseapp.poseapp_kinesis import PoseAppWKinesis

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class KinesisProcessor(processor.RecordProcessorBase):
    """
    A KinesisProcessor processes data from a shard in a stream. Its methods will be called with this pattern:
    * initialize will be called once
    * process_records will be called zero or more times
    * shutdown will be called if this MultiLangDaemon instance loses the lease to this shard, or the shard ends due
        a scaling change.
    """

    def __init__(self, tf_op, w, h, n_workers, result_stream, n_shards=1):

        self.n_shards = n_shards
        self._SLEEP_SECONDS = 5
        self._CHECKPOINT_RETRIES = 5
        self._CHECKPOINT_FREQ_SECONDS = 60
        self._largest_seq = (None, None)
        self._largest_sub_seq = None
        self._last_checkpoint_time = None

        self.tf_op = tf_op
        self.h = h
        self.w = w
        self.worker_mgr = futures.ThreadPoolExecutor(max_workers=n_workers)
        self.client = boto3.client("kinesis", region_name='ap-southeast-1')
        self.result_stream = result_stream
        self.put_queue = Queue()
        self.th_signal = threading.Event()
        self.th_put_stream = None
        self.seq_num_of_prev_put_rec = None

        # self.start_process = False

    def initialize(self, initialize_input):
        """
        Called once by a KCLProcess before any calls to process_records
        :param amazon_kclpy.messages.InitializeInput initialize_input: Information about the lease that this record
            processor has been assigned.
        """
        self._largest_seq = (None, None)
        self._last_checkpoint_time = time.time()

        # logger.debug("Intializing thread to put results back to stream.")
        # self.th_signal.clear()
        # self.th_put_stream = threading.Thread(target=self._put_result_th)
        # self.th_put_stream.start()

    def checkpoint(self, checkpointer, sequence_number=None, sub_sequence_number=None):
        """
        Checkpoints with retries on retryable exceptions.
        :param amazon_kclpy.kcl.Checkpointer checkpointer: the checkpointer provided to either process_records
            or shutdown
        :param str or None sequence_number: the sequence number to checkpoint at.
        :param int or None sub_sequence_number: the sub sequence number to checkpoint at.
        """
        for n in range(0, self._CHECKPOINT_RETRIES):
            try:
                checkpointer.checkpoint(sequence_number, sub_sequence_number)
                return
            except kcl.CheckpointError as e:
                if 'ShutdownException' == e.value:
                    #
                    # A ShutdownException indicates that this record processor should be shutdown. This is due to
                    # some failover event, e.g. another MultiLangDaemon has taken the lease for this shard.
                    #
                    print('Encountered shutdown exception, skipping checkpoint')
                    return
                elif 'ThrottlingException' == e.value:
                    #
                    # A ThrottlingException indicates that one of our dependencies is is over burdened, e.g. too many
                    # dynamo writes. We will sleep temporarily to let it recover.
                    #
                    if self._CHECKPOINT_RETRIES - 1 == n:
                        sys.stderr.write('Failed to checkpoint after {n} attempts, giving up.\n'.format(n=n))
                        return
                    else:
                        print('Was throttled while checkpointing, will attempt again in {s} seconds'
                              .format(s=self._SLEEP_SECONDS))
                elif 'InvalidStateException' == e.value:
                    sys.stderr.write('MultiLangDaemon reported an invalid state while checkpointing.\n')
                else:  # Some other error
                    sys.stderr.write('Encountered an error while checkpointing, error was {e}.\n'.format(e=e))
            time.sleep(self._SLEEP_SECONDS)

    def process_record(self, data, partition_key, sequence_number, sub_sequence_number):
        """
        Called for each record that is passed to process_records.
        :param str data: The blob of data that was contained in the record.
        :param str partition_key: The key associated with this recod.
        :param int sequence_number: The sequence number associated with this record.
        :param int sub_sequence_number: the sub sequence number associated with this record.
        """
        ####################################
        # Insert your processing logic here
        ####################################
        try:
            data = pickle.loads(data)
            future = self.worker_mgr.submit(self._worker_th, data['frame'],data['frame_no'])  # submit record to worker thread pool
            self.put_queue.put(future)

        except Exception as e:
            logger.debug(traceback.format_exc())

    def should_update_sequence(self, sequence_number, sub_sequence_number):
        """
        Determines whether a new larger sequence number is available
        :param int sequence_number: the sequence number from the current record
        :param int sub_sequence_number: the sub sequence number from the current record
        :return boolean: true if the largest sequence should be updated, false otherwise
        """
        return self._largest_seq == (None, None) or sequence_number > self._largest_seq[0] or \
               (sequence_number == self._largest_seq[0] and sub_sequence_number > self._largest_seq[1])

    def process_records(self, process_records_input):
        """
        Called by a KCLProcess with a list of records to be processed and a checkpointer which accepts sequence numbers
        from the records to indicate where in the stream to checkpoint.
        :param amazon_kclpy.messages.ProcessRecordsInput process_records_input: the records, and metadata about the
            records.
        """
        try:
            for record in process_records_input.records:
                data = record.binary_data
                seq = int(record.sequence_number)
                sub_seq = record.sub_sequence_number
                key = record.partition_key
                self.process_record(data, key, seq, sub_seq)

                if self.should_update_sequence(seq, sub_seq):
                    self._largest_seq = (seq, sub_seq)

            #
            # Checkpoints every self._CHECKPOINT_FREQ_SECONDS seconds
            #
            if time.time() - self._last_checkpoint_time > self._CHECKPOINT_FREQ_SECONDS:
                self.checkpoint(process_records_input.checkpointer, str(self._largest_seq[0]), self._largest_seq[1])
                self._last_checkpoint_time = time.time()

        except Exception as e:
            sys.stderr.write("Encountered an exception while processing records. Exception was {e}\n".format(e=e))

    def shutdown(self, shutdown_input):
        """
        Called by a KCLProcess instance to indicate that this record processor should shutdown. After this is called,
        there will be no more calls to any other methods of this record processor.
        As part of the shutdown process you must inspect :attr:`amazon_kclpy.messages.ShutdownInput.reason` to
        determine the steps to take.
            * Shutdown Reason ZOMBIE:
                **ATTEMPTING TO CHECKPOINT ONCE A LEASE IS LOST WILL FAIL**
                A record processor will be shutdown if it loses its lease.  In this case the KCL will terminate the
                record processor.  It is not possible to checkpoint once a record processor has lost its lease.
            * Shutdown Reason TERMINATE:
                **THE RECORD PROCESSOR MUST CHECKPOINT OR THE KCL WILL BE UNABLE TO PROGRESS**
                A record processor will be shutdown once it reaches the end of a shard.  A shard ending indicates that
                it has been either split into multiple shards or merged with another shard.  To begin processing the new
                shard(s) it's required that a final checkpoint occurs.
        :param amazon_kclpy.messages.ShutdownInput shutdown_input: Information related to the shutdown request
        """
        try:
            if shutdown_input.reason == 'TERMINATE':
                # Checkpointing with no parameter will checkpoint at the
                # largest sequence number reached by this processor on this
                # shard id
                print('Was told to terminate, will empty the data in the streams, and reset checkpoint.')
                self.checkpoint(shutdown_input.checkpointer, None)
            else:  # reason == 'ZOMBIE'
                print('Shutting down due to failover. Will not checkpoint.')
        except:
            pass

        # logger.debug("Joining put stream thread back.")

        # self.th_signal.set()
        # self.th_put_stream.join()
        # self.put_queue.empty()

    def _worker_th(self, frame, frame_no):

        logger.debug("worker processing")
        humans = self.tf_op.inference(frame, resize_to_default=(self.w > 0 and self.h > 0), upsample_size=4.0)
        pose = ''
        if len(humans) > 0:
            humans.sort(key=lambda x: x.score, reverse=True)
            humans = humans[:1]  # get the human with the highest score
            frame = TfPoseEstimator.draw_humans(frame, humans)
            frame, pose = PoseAppWKinesis.identify_body_gestures(frame, humans[0])

        frame_package = {
            'frame_no': frame_no,
            'frame': frame,
            'pose': pose
        }

        partition_key = random.randint(1,self.n_shards)

        self.client.put_record(
            StreamName=self.result_stream,
            Data=pickle.dumps(frame_package),
            PartitionKey=str(partition_key)
        )
        logger.debug("Sent frame package to part {}".format(partition_key))
        logger.debug("worker finish")
        # return frame_package
        # print("pose: {}".format(frame_package["pose"]))

    # def _put_result_th(self):
    #     logger.debug("Started put results back to stream thread...")
    #
    #     while True and not self.th_signal.is_set():
    #         response = {}
    #
    #         try:
    #             future = self.put_queue.get(timeout=5)
    #             frame_package = future.result(timeout=5)
    #
    #             if self.seq_num_of_prev_put_rec is not None:
    #                 response = self.client.put_record(
    #                     StreamName=self.result_stream,
    #                     Data=pickle.dumps(frame_package),
    #                     PartitionKey="resultframes",
    #                     SequenceNumberForOrdering=self.seq_num_of_prev_put_rec
    #                 )
    #             else:
    #                 response = self.client.put_record(
    #                     StreamName=self.result_stream,
    #                     Data=pickle.dumps(frame_package),
    #                     PartitionKey=str()
    #                 )
    #
    #             self.seq_num_of_prev_put_rec = response['SequenceNumber']
    #             logger.debug("Sent frame package.")
    #
    #         except Empty:
    #             logger.debug("Future queue is empty.")
    #             continue
    #
    #         except concurrent.futures.TimeoutError:
    #             logger.debug("Waiting for worker thread to complete frame to send.")
    #             continue
    #
    #         except Exception as e:
    #             logger.debug("Error Putting record {}".format(traceback.format_exc()))
    #             continue
    #
    #     logger.debug("Ending thread...")





