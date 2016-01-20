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


class MockMethod(object):
    def __init__(self):
        self._calls = []

    def clear(self):
        self._calls = []

    def call_list(self):
        return self._calls


class MockServerRun(MockMethod):
    def __init__(self):
        MockMethod.__init__(self)

    def __call__(self, cmd, user=None, sudo=False, ignore_error=False,
                 success_status=(0,), error_callback=None):
        user = user or 'root'
        self._calls.append({'cmd': cmd,
                            'user': user,
                            'ignore_error': ignore_error,
                            'success_status': success_status,
                            'error_callback': error_callback})
        return "ok", 0


class MockServerCreateFile(MockMethod):
    def __init__(self):
        MockMethod.__init__(self)

    def __call__(self, path, content, mode='w', user='root'):
        self._calls.append({'path:': path,
                            'content': content,
                            'mode': mode,
                            'user': user})
