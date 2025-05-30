# Copyright 2022, FedML.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Arguments."""

import argparse
import os
from os import path
import logging

import yaml

from fedml.constants import (
    FEDML_TRAINING_PLATFORM_SIMULATION,
    FEDML_SIMULATION_TYPE_MPI,
    FEDML_SIMULATION_TYPE_SP,
    FEDML_TRAINING_PLATFORM_CROSS_SILO,
    FEDML_TRAINING_PLATFORM_CROSS_DEVICE,
    FEDML_CROSS_SILO_SCENARIO_HIERARCHICAL,
)


def add_args():
    parser = argparse.ArgumentParser(description="FedML")
    parser.add_argument("--yaml_config_file","--cf",help="yaml configuration file",type=str,default="", )

    # default arguments
    parser.add_argument("--run_id", type=str, default="0")

    # default arguments
    parser.add_argument("--rank", type=int, default=0)

    # default arguments
    parser.add_argument("--local_rank", type=int, default=0)

    # For hierarchical scenario
    parser.add_argument("--node_rank", type=int, default=0)

    # default arguments
    parser.add_argument("--role", type=str, default="client")

    args, unknown = parser.parse_known_args()  # args是上面哪些参数，unknown为空
    return args


class Arguments:
    """Argument class which contains all arguments from yaml config and constructs additional arguments"""

    # 包括yaml配置文件中的所有参数，并构造额外参数
    def __init__(self, cmd_args, training_type=None, comm_backend=None, override_cmd_args=True):
        # set the command line arguments
        # {dict:6}{'yaml_config_file': '', 'run_id': '0', 'rank': 0, 'local_rank': 0, 'node_rank': 0, 'role': 'client'}
        cmd_args_dict = cmd_args.__dict__
        for arg_key, arg_val in cmd_args_dict.items():  # 依次取6个属性和它们的值
            setattr(self, arg_key, arg_val)

        self.get_default_yaml_config(cmd_args, training_type, comm_backend)
        if not override_cmd_args:
            # reload cmd args again
            for arg_key, arg_val in cmd_args_dict.items():
                setattr(self, arg_key, arg_val)

    def load_yaml_config(self, yaml_path):
        with open(yaml_path, "r") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                raise ValueError("Yaml error - check yaml file")

    def get_default_yaml_config(self, cmd_args, training_type=None, comm_backend=None):
        if cmd_args.yaml_config_file == "":
            path_current_file = path.abspath(path.dirname(__file__))  # 获取当前文件的路径
            if (
                    training_type == FEDML_TRAINING_PLATFORM_SIMULATION  # 'simulation'
                    and comm_backend == FEDML_SIMULATION_TYPE_SP  # 'sp'
            ):
                config_file = path.join(
                    # path_current_file, "config/simulation_sp/fedml_config.yaml"
                    path_current_file, "./fedml_config.yaml"  # 配置文件的路径
                )
                cmd_args.yaml_config_file = config_file  # 指定config_file
                print("training_type == FEDML_TRAINING_PLATFORM_SIMULATION and comm_backend == FEDML_SIMULATION_TYPE_SP")
            elif (
                    training_type == FEDML_TRAINING_PLATFORM_SIMULATION
                    and comm_backend == FEDML_SIMULATION_TYPE_MPI
            ):
                config_file = path.join(path_current_file, "config/simulaton_mpi/fedml_config.yaml")
                cmd_args.yaml_config_file = config_file
                print("training_type == FEDML_TRAINING_PLATFORM_SIMULATION and comm_backend == FEDML_SIMULATION_TYPE_MPI")
            elif training_type == FEDML_TRAINING_PLATFORM_CROSS_SILO:
                print("training_type == FEDML_TRAINING_PLATFORM_CROSS_SILO")
            elif training_type == FEDML_TRAINING_PLATFORM_CROSS_DEVICE:
                print("training_type == FEDML_TRAINING_PLATFORM_CROSS_DEVICE")
            else:
                raise Exception("no such a platform. training_type = {}, backend = {}".format(training_type, comm_backend))
        self.yaml_paths = [cmd_args.yaml_config_file]
        # Load all arguments from yaml config
        # https://www.cloudbees.com/blog/yaml-tutorial-everything-you-need-get-started
        configuration = self.load_yaml_config(cmd_args.yaml_config_file)
        # Override class attributes from current yaml config
        self.set_attr_from_config(configuration)
        if cmd_args.yaml_config_file == "":
            path_current_file = path.abspath(path.dirname(__file__))
            if (training_type == FEDML_TRAINING_PLATFORM_SIMULATION and comm_backend == FEDML_SIMULATION_TYPE_SP):
                pass
            elif (training_type == FEDML_TRAINING_PLATFORM_SIMULATION and comm_backend == FEDML_SIMULATION_TYPE_MPI):
                self.gpu_mapping_file = path.join(path_current_file, "config/simulaton_mpi/gpu_mapping.yaml")
            elif training_type == FEDML_TRAINING_PLATFORM_CROSS_SILO:
                pass
            elif training_type == FEDML_TRAINING_PLATFORM_CROSS_DEVICE:
                pass
            else:
                pass
        if hasattr(self, "training_type"):
            training_type = self.training_type

        if training_type == FEDML_TRAINING_PLATFORM_CROSS_SILO:
            if (hasattr(self, "scenario") and self.scenario == FEDML_CROSS_SILO_SCENARIO_HIERARCHICAL):
                # Add extra configs specific to silos or server
                self.rank = int(self.rank)
                if self.rank == 0:
                    extra_config_path = self.server_config_path
                else:
                    extra_config_path = self.client_silo_config_paths[self.rank - 1]
                extra_config = self.load_yaml_config(extra_config_path)
                self.set_attr_from_config(extra_config)

        return configuration

    def set_attr_from_config(self, configuration):
        for _, param_family in configuration.items():
            for key, val in param_family.items():
                setattr(self, key, val)


def load_arguments(training_type=None, comm_backend=None):
    cmd_args = add_args()
    # Load all arguments from YAML config file
    args = Arguments(cmd_args, training_type, comm_backend)

    if not hasattr(args, "worker_num"):
        args.worker_num = args.client_num_per_round

    # os.path.expanduser() method in Python is used
    # to expand an initial path component ~( tilde symbol)
    # or ~user in the given path to user’s home directory.
    if hasattr(args, "data_cache_dir"):
        args.data_cache_dir = os.path.expanduser(args.data_cache_dir)
    if hasattr(args, "data_file_path"):
        args.data_file_path = os.path.expanduser(args.data_file_path)
    if hasattr(args, "partition_file_path"):
        args.partition_file_path = os.path.expanduser(args.partition_file_path)
    if hasattr(args, "part_file"):
        args.part_file = os.path.expanduser(args.part_file)

    args.rank = int(args.rank)
    return args
