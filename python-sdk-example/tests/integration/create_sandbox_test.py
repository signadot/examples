from __future__ import print_function

import os
import random
import string
import time
import unittest

import requests
import timeout_decorator
from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, SandboxForkEndpoint, SandboxEnvVar, Sandbox, SandboxSpec
from signadot_sdk.rest import ApiException


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


class TestBasic(unittest.TestCase):
    SIGNADOT_CLUSTER_NAME = os.getenv('SIGNADOT_CLUSTER_NAME')
    if SIGNADOT_CLUSTER_NAME is None:
        raise OSError("SIGNADOT_CLUSTER_NAME is not set")

    SIGNADOT_ORG = os.getenv('SIGNADOT_ORG')
    if SIGNADOT_ORG is None:
        raise OSError("SIGNADOT_ORG is not set")

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    configuration = Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    sandboxes_api = SandboxesApi(ApiClient(configuration))
    sandbox_name = None
    endpoint_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    @timeout_decorator.timeout(120)
    def setUpClass(cls):
        route_fork = SandboxFork(
            fork_of=SandboxForkOf(
                kind="Deployment",
                name="route",
                namespace="hotrod"
            ),
            customizations=SandboxCustomizations(
                images=[
                    SandboxImage(image="signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd")
                ],
                env=[
                    SandboxEnvVar(name="abc", value="xyz")
                ]
            ),
            endpoints=[
                SandboxForkEndpoint(
                    name="hotrod-route",
                    port=8083,
                    protocol="http"
                )
            ]
        )
        cls.sandbox_name = "test-ws-{}".format(get_random_string(5))
        request = Sandbox(
            spec=SandboxSpec(
                description="Sample sandbox created using Python SDK",
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                forks=[route_fork]
            )
        )

        try:
            sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-route", sandbox.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-route` missing")
        cls.endpoint_url = filtered_endpoints[0].url

        # Code block to wait until sandbox is ready
        while not sandbox.status.ready:
            time.sleep(5)
            sandbox = cls.sandboxes_api.get_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)

    def test_valid_result(self):
        pickup = "123"
        dropoff = "456"
        service_url = "{}/route?pickup={}&dropoff={}".format(self.endpoint_url, pickup, dropoff)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["Pickup"], pickup, "Pickup must equal {}".format(pickup))
        self.assertEqual(data["Dropoff"], dropoff, "Dropoff must equal {}".format(dropoff))
        self.assertGreater(data["ETA"], -1, "ETA must be non-negative")

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)


if __name__ == '__main__':
    unittest.main()
