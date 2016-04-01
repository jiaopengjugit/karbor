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

import os
from swiftclient import ClientException
import tempfile


class FakeSwiftClient(object):
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def connection(cls, *args, **kargs):
        return FakeSwiftConnection()


class FakeSwiftConnection(object):
    def __init__(self, *args, **kwargs):
        self.swiftdir = tempfile.mkdtemp()

    def put_container(self, container):
        container_dir = self.swiftdir + "/" + container
        if os.path.exists(container_dir) is True:
            return
        else:
            os.makedirs(container_dir)

    def get_container(self, container, prefix, limit, marker):
        container_dir = self.swiftdir + "/" + container
        body = []
        if prefix:
            objects_dir = container_dir + "/" + prefix
        else:
            objects_dir = container_dir
        for f in os.listdir(objects_dir):
            if os.path.isfile(objects_dir + "/" + f):
                body.append({"name": f})
            else:
                body.append({"subdir": f})
        return None, body

    def put_object(self, container, obj, contents, headers=None):
        container_dir = self.swiftdir + "/" + container
        obj_file = container_dir + "/" + obj
        obj_dir = obj_file[0:obj_file.rfind("/")]
        if os.path.exists(container_dir) is True:
            if os.path.exists(obj_dir) is False:
                os.makedirs(obj_dir)
            with open(obj_file, "w") as f:
                f.write(contents)
            return
        else:
            raise ClientException("error_container")

    def get_object(self, container, obj):
        container_dir = self.swiftdir + "/" + container
        obj_file = container_dir + "/" + obj
        if os.path.exists(container_dir) is True:
            if os.path.exists(obj_file) is True:
                with open(obj_file, "r") as f:
                    return {}, f.read()
            else:
                raise ClientException("error_obj")
        else:
            raise ClientException("error_container")

    def delete_object(self, container, obj):
        container_dir = self.swiftdir + "/" + container
        obj_file = container_dir + "/" + obj
        if os.path.exists(container_dir) is True:
            if os.path.exists(obj_file) is True:
                os.remove(obj_file)
            else:
                raise ClientException("error_obj")
        else:
            raise ClientException("error_container")

    def update_object(self, container, obj, contents):
        container_dir = self.swiftdir + "/" + container
        obj_file = container_dir + "/" + obj
        if os.path.exists(container_dir) is True:
            if os.path.exists(obj_file) is True:
                with open(obj_file, "w") as f:
                    f.write(contents)
                    return
            else:
                raise ClientException("error_obj")
        else:
            raise ClientException("error_container")
