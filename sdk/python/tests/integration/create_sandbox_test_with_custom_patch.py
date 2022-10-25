from __future__ import print_function

import os
import random
import string
import time
import unittest

import requests
import timeout_decorator

from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, SandboxForkEndpoint, Sandbox, SandboxSpec, SandboxCustomPatch, SandboxTTL
from signadot_sdk.rest import ApiException


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


class TestBasic(unittest.TestCase):
    CUSTOM_PATCH = """
    spec:
      template:
        spec:
          containers:
          - name: hotrod
            env:
            - name: PATCH_TEST_VAR
              value: "{}"
    """
    HOTROD_TEST_IMAGE = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0"
    SIGNADOT_ORG = os.getenv("SIGNADOT_ORG")
    CLUSTER_NAME = os.getenv("SIGNADOT_CLUSTER_NAME")
    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_ORG is None:
        raise OSError("SIGNADOT_ORG is not set")
    if CLUSTER_NAME is None:
        raise OSError("SIGNADOT_CLUSTER_NAME is not set")
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    configuration = Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    sandboxes_api = SandboxesApi(ApiClient(configuration))
    sandbox_name = None
    env_var_value = None
    endpoint_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    @timeout_decorator.timeout(120)
    def setUpClass(cls):
        cls.env_var_value = get_random_string(5)

        customer_fork = SandboxFork(
            fork_of=SandboxForkOf(
                kind="Deployment",
                name="customer",
                namespace="hotrod"
            ),
            customizations=SandboxCustomizations(
                images=[
                    SandboxImage(image=cls.HOTROD_TEST_IMAGE)
                ],
                patch=SandboxCustomPatch(
                    type="strategic",
                    value=cls.CUSTOM_PATCH.format(cls.env_var_value)
                )
            ),
            endpoints=[
                SandboxForkEndpoint(
                    name="hotrod-customer",
                    port=8081,
                    protocol="http"
                )
            ]
        )
        cls.sandbox_name = "custom-patch-test-{}".format(get_random_string(5))
        request = Sandbox(
            spec=SandboxSpec(
                description="Python SDK: sandbox creation with custom patch example",
                ttl=SandboxTTL(duration="10m"),
                cluster=cls.CLUSTER_NAME,
                forks=[customer_fork]
            )
        )

        try:
            sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-customer", sandbox.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-customer` missing")
        cls.endpoint_url = filtered_endpoints[0].url

        # Code block to wait until sandbox is ready
        while not sandbox.status.ready:
            time.sleep(5)
            sandbox = cls.sandboxes_api.get_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)

    def test_valid_result(self):
        service_url = "{}/customer?customer=392".format(self.endpoint_url)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["PatchVar"], self.env_var_value, "PatchVar must equal {}".format(self.env_var_value))

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)


if __name__ == '__main__':
    unittest.main()
