# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Red Hat, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import sys


def setup_logging(extra_handlers=(), config_file='chainsaw.log'):
    logger = logging.getLogger('tripleohelper')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s::%(levelname)s::%(message)s")
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(config_file, mode='w')
    file_handler.setFormatter(formatter)

    try:
        import colorlog

        colored_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s::%(levelname)s::%(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red'
            }
        )
        stream_handler.setFormatter(colored_formatter)
    except ImportError:
        pass
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    for handler in extra_handlers:
        logger.addHandler(handler)
