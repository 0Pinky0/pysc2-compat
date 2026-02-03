# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Setuptools entry point for custom build command."""

from setuptools import setup
from setuptools.command.build import build as _build


class BuildCommand(_build):

    def initialize_options(self):
        super().initialize_options()
        # To avoid conflicting with the Bazel BUILD file.
        self.build_base = '_build'


setup(cmdclass={'build': BuildCommand})
