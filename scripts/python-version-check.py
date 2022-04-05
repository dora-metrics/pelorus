# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from sys import executable, exit, version_info

PYTHON_VER_MIN = (3, 9)
PYTHON_VER_MAX = (3, 10)

SYS_PYTHON_VER = (version_info.major, version_info.minor)

if not PYTHON_VER_MIN <= SYS_PYTHON_VER <= PYTHON_VER_MAX:
    print(
        "{} needs to be between {}.{} and {}.{}, but was {}.{}".format(
            executable, *PYTHON_VER_MIN, *PYTHON_VER_MAX, *SYS_PYTHON_VER
        )
    )
    exit(1)
