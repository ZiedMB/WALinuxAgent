# Copyright 2014 Microsoft Corporation
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
#
# Requires Python 2.4+ and Openssl 1.0+
#

import unittest

import azurelinuxagent.common.protocol.restapi as restapi
import azurelinuxagent.common.protocol.wire as wire
from tests.protocol.mockwiredata import WireProtocolData, DATA_FILE
from tests.tools import *

wireserver_url = "168.63.129.16"
sas_url = "http://sas_url"
api_versions = '["2015-09-01"]'
container_id = "dummy_container_id"
config_name = "dummy_config_name.xml"

class TestHostPlugin(AgentTestCase):

    def test_fallback(self):
        """
        Validate fallback to upload status using HostGAPlugin is happening when status reporting via
        default method is unsuccessful
        """
        test_goal_state = wire.GoalState(WireProtocolData(DATA_FILE).goal_state)

        with patch.object(wire.HostPluginProtocol,
                          "put_vm_status") as patch_put:
            with patch.object(wire.StatusBlob, "upload") as patch_upload:
                patch_upload.return_value = False
                wire_protocol_client = wire.WireProtocol(wireserver_url).client
                # Mock get_goal_state() as it is called while uploading status using HostGAPlugin
                wire_protocol_client.get_goal_state = Mock(return_value = test_goal_state)
                wire_protocol_client.ext_conf = wire.ExtensionsConfig(None)
                wire_protocol_client.ext_conf.status_upload_blob = sas_url
                wire_protocol_client.upload_status_blob()
                self.assertTrue(patch_put.call_count == 1,
                                "Fallback was not engaged")
                self.assertTrue(patch_put.call_args[0][1] == sas_url)
                self.assertTrue(patch_put.call_args[0][2] == test_goal_state.container_id)
                self.assertTrue(patch_put.call_args[0][3] == test_goal_state.role_instance_config_name)

    def test_validate_http_request(self):
        """Validate correct set of data is sent to HostGAPlugin when reporting VM status"""
        from azurelinuxagent.common.protocol.hostplugin import API_VERSION
        from azurelinuxagent.common.utils import restutil
        exp_method = 'PUT'
        exp_url = 'http://{0}:32526/status'.format(wireserver_url)
        exp_data = '{"content": "UmVhZHk=", "headers": [{"headerName": ' \
                   '"x-ms-version", "headerValue": "2014-02-14"}, ' \
                   '{"headerName": "x-ms-blob-type", "headerValue": null}], ' \
                   '"requestUri": "http://sas_url"}'
        with patch.object(restutil, "http_request") as patch_http:
            wire_protocol_client = wire.WireProtocol(wireserver_url).client
            plugin = wire_protocol_client.host_plugin
            blob = wire_protocol_client.status_blob
            blob.vm_status = restapi.VMStatus()
            blob.vm_status.vmAgent.status = 'Ready'
            with patch.object(plugin, 'get_api_versions') as patch_api:
                patch_api.return_value = API_VERSION
                plugin.put_vm_status(blob, sas_url, container_id, config_name)
                self.assertTrue(patch_http.call_count == 1)
                self.assertTrue(patch_http.call_args[0][0] == exp_method)
                self.assertTrue(patch_http.call_args[0][1] == exp_url)
                self.assertTrue(patch_http.call_args[0][2] == exp_data)

                #Assert headers
                headers = patch_http.call_args[1]['headers']
                self.assertEqual(headers['x-ms-containerid'], container_id)
                self.assertEqual(headers['x-ms-host-config-name'], config_name)

    def test_no_fallback(self):
        """
        Validate fallback to upload status using HostGAPlugin is not happening when status reporting via
        default method is successful
        """
        with patch.object(wire.HostPluginProtocol,
                          "put_vm_status") as patch_put:
            with patch.object(wire.StatusBlob, "upload") as patch_upload:
                patch_upload.return_value = True
                wire_protocol_client = wire.WireProtocol(wireserver_url).client
                wire_protocol_client.ext_conf = wire.ExtensionsConfig(None)
                wire_protocol_client.ext_conf.status_upload_blob = sas_url
                wire_protocol_client.upload_status_blob()
                self.assertTrue(patch_put.call_count == 0,
                                "Fallback was engaged")

    def test_validate_http_put(self):
        """Validate correct set of data is sent to HostGAPlugin when reporting VM status"""
        expected_url = "http://168.63.129.16:32526/status"
        expected_headers = {'x-ms-version': '2015-09-01',
                            "Content-type": "application/json",
                            "x-ms-containerid": container_id,
                            "x-ms-host-config-name": config_name}
        expected_content = '{"content": "b2s=", ' \
                           '"headers": [{"headerName": "x-ms-version", ' \
                           '"headerValue": "2014-02-14"}, ' \
                           '{"headerName": "x-ms-blob-type", "headerValue": ' \
                           '"BlockBlob"}], ' \
                           '"requestUri": "http://sas_url"}'

        host_client = wire.HostPluginProtocol(wireserver_url)
        self.assertFalse(host_client.is_initialized)
        self.assertTrue(host_client.api_versions is None)
        status_blob = wire.StatusBlob(None)
        status_blob.vm_status = restapi.VMStatus()
        status_blob.vm_status.vmAgent.status = 'ok'
        status_blob.type = "BlockBlob"
        with patch.object(wire.HostPluginProtocol,
                          "get_api_versions") as patch_get:
            patch_get.return_value = api_versions
            with patch.object(restapi.restutil, "http_put") as patch_put:
                patch_put.return_value = MagicMock()
                host_client.put_vm_status(status_blob, sas_url, container_id, config_name)
                self.assertTrue(host_client.is_initialized)
                self.assertFalse(host_client.api_versions is None)
                self.assertTrue(patch_put.call_count == 1)
                self.assertTrue(patch_put.call_args[0][0] == expected_url)
                self.assertTrue(patch_put.call_args[0][1] == expected_content)
                self.assertTrue(patch_put.call_args[0][2] == expected_headers)


if __name__ == '__main__':
    unittest.main()
