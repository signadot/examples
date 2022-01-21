from __future__ import print_function

import time
import unittest
import os
import random
import requests
import signadot_sdk
import string
from signadot_sdk.rest import ApiException

def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))

class TestBasic(unittest.TestCase):
    org_name = 'signadot'

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    configuration = signadot_sdk.Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    workspaces_api = signadot_sdk.WorkspacesApi(signadot_sdk.ApiClient(configuration))
    workspace_id = None
    preview_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    def setUpClass(cls):
        route_fork = signadot_sdk.WorkspaceFork(
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="route",
                namespace="hotrod"
            ),
            customizations=signadot_sdk.WorkspaceCustomizations(
                images=[
                    signadot_sdk.Image(image="signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3")
                ],
                env=[
                    signadot_sdk.EnvOp(name="abc", value="xyz", operation="upsert")
                ]
            ),
            endpoints=[
                signadot_sdk.ForkEndpoint(
                    name="hotrod-route",
                    port=8083,
                    protocol="http"
                )
            ]
        )
        request = signadot_sdk.CreateWorkspaceRequest(
            name="test-ws-{}".format(get_random_string(5)),
            description="Sample workspace created using Python SDK",
            cluster="demo",
            forks=[route_fork]
        )

        try:
            api_response = cls.workspaces_api.create_new_workspace(cls.org_name, request)
        except ApiException as e:
            print("Exception creating a workspace: %s\n" % e)

        cls.workspace_id = api_response.workspace_id

        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-route", api_response.preview_endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-route` missing")
        preview_endpoint = filtered_endpoints[0]
        cls.preview_url = preview_endpoint.preview_url

        workspace_ready = False
        max_attempts = 10
        print("Checking workspace readiness")
        for i in range(1, max_attempts):
            print("Attempt: {}/{}".format(i, max_attempts))
            workspace_ready = cls.workspaces_api.get_workspace_ready(cls.org_name, cls.workspace_id).ready
            if workspace_ready:
                print("Workspace is ready!")
                break
            time.sleep(5)

        if not workspace_ready:
            raise RuntimeError("Workspace didn't get to Ready state")

    def test_valid_result(self):
        pickup = "123"
        dropoff = "456"
        service_url = "{}/route?pickup={}&dropoff={}".format(self.preview_url, pickup, dropoff)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["Pickup"], pickup, "Pickup must equal {}".format(pickup))
        self.assertEqual(data["Dropoff"], dropoff, "Dropoff must equal {}".format(dropoff))
        self.assertGreater(data["ETA"], -1, "ETA must be non-negative")

    @classmethod
    def tearDownClass(cls):
        cls.workspaces_api.delete_workspace_by_id(cls.org_name, cls.workspace_id)

if __name__ == '__main__':
    unittest.main()
