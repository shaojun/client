#!/usr/bin/env python
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
from functools import partial
import os
import sys
import base64_image_client

from kafka import KafkaConsumer
import json
import uuid
import numpy as np

infer_server_url = None
infer_server_protocol = None
infer_model_name = None
infer_model_version = None
infer_server_comm_output_verbose = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v',
                        '--infer-server-comm-output-verbose',
                        action="store_true",
                        required=False,
                        default=False,
                        help='Enable verbose output')
    parser.add_argument('-a',
                        '--async',
                        dest="async_set",
                        action="store_true",
                        required=False,
                        default=False,
                        help='Use asynchronous inference API')
    parser.add_argument('--streaming',
                        action="store_true",
                        required=False,
                        default=False,
                        help='Use streaming inference API. ' +
                             'The flag is only available with gRPC protocol.')
    parser.add_argument('-m',
                        '--infer-model-name',
                        type=str,
                        required=False,
                        default="bicycletypenet_tao",
                        help='Name of model')
    parser.add_argument('-x',
                        '--infer-model-version',
                        type=str,
                        required=False,
                        default="",
                        help='Version of model. Default is to use latest version.')
    parser.add_argument('-b',
                        '--batch-size',
                        type=int,
                        required=False,
                        default=1,
                        help='Batch size. Default is 1.')
    parser.add_argument('-c',
                        '--classes',
                        type=int,
                        required=False,
                        default=1,
                        help='Number of class results to report. Default is 1.')
    parser.add_argument('-s',
                        '--scaling',
                        type=str,
                        choices=['NONE', 'INCEPTION', 'VGG'],
                        required=False,
                        default='NONE',
                        help='Type of scaling to apply to image pixels. Default is NONE.')
    parser.add_argument('-u',
                        '--infer-server-url',
                        type=str,
                        required=False,
                        default='localhost:8000',
                        help='Inference server URL. Default is localhost:8000.')
    parser.add_argument('-k',
                        '--kafka-server-url',
                        type=str,
                        required=False,
                        default='dev-iot.ipos.biz:9092',
                        help='kafka server URL. Default is xxx:9092.')
    parser.add_argument('-i',
                        '--infer-server-protocol',
                        type=str,
                        required=False,
                        default='HTTP',
                        help='Protocol (HTTP/gRPC) used to communicate with ' +
                             'the inference service. Default is HTTP.')

    FLAGS = parser.parse_args()

consumer = KafkaConsumer(
    bootstrap_servers=FLAGS.kafka_server_url,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=str(uuid.uuid1()),
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

consumer.subscribe(pattern=".*")
# do a dummy poll to retrieve some message
consumer.poll()

# go to end of the stream
consumer.seek_to_end()

for event in consumer:
    event_data = event.value
    for obj in event_data["objects"]:
        sections = obj.split('|')
        if "Vehicle|#|DoorWarningSign" in obj:
            # detected DoorSign
            # report an alarm to webservice
            # webservice.post(Priority.Info, "board with uniqueId: " + event_data['sensorId'] + " detected a doorsign, indicates the door is in closed state.")
            pass
        elif "Vehicle|#|TwoWheeler" in obj:
            print("A suspect electric-bicycle is detected, will send to infer server to further make sure of it...")
            # the last but one is the detected object image file with base64 encoded text,
            # and the section is prefixed with-> base64_image_data:
            cropped_base64_image_file_text = sections[len(sections) - 2][len("base64_image_data:")]
            infer_results = base64_image_client.infer(FLAGS.infer_server_comm_output_verbose, FLAGS.async_set,
                                                      FLAGS.streaming,
                                                      FLAGS.infer_model_name, FLAGS.infer_model_version,
                                                      FLAGS.batch_size,
                                                      FLAGS.classes, FLAGS.scaling, FLAGS.infer_server_url,
                                                      FLAGS.infer_server_protocol,
                                                      [cropped_base64_image_file_text])

            is_model_support_batching = True
            for infer_result in infer_results:
                for results in infer_result:
                    if not is_model_support_batching:
                        results = [results]
                    for result in results:
                        if infer_result.dtype.type == np.object_:
                            cls = "".join(chr(x) for x in result).split(':')
                        else:
                            cls = result.split(':')
                        print("    conf: {} (label_index: {}) = label: {}".format(cls[0], cls[1], cls[2]))
            # above print sample like below, which means the infer server is 72.4619% sure it's a CUP
            #       conf: 0.724619 (label_index: 666) = label: CUP

            # report an alarm to webservice
            # webservice.post(Priority.Error, "board with uniqueId: " + event_data['sensorId'] + " detected an electric-bicycle entering elevator, please keep the door opening")
        elif "Person|#" in obj:
            # detected Person
            # report an alarm to webservice
            # webservice.post(Priority.Info, "board with uniqueId: " + event_data['sensorId'] + " detected a person, indicates there's a people in elevator.")
            pass
        elif "Vehicle|#|Bicycle" in obj:
            # detected Bicycle
            pass
