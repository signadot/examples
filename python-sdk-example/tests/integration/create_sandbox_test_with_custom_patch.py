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
    ORG_NAME = os.getenv("SIGNADOT_ORG")
    CLUSTER_NAME = os.getenv("SIGNADOT_CLUSTER_NAME")
    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if ORG_NAME is None:
        raise OSError("SIGNADOT_ORG is not set")
    if CLUSTER_NAME is None:
        raise OSError("SIGNADOT_CLUSTER_NAME is not set")
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    configuration = signadot_sdk.Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    sandboxes_api = signadot_sdk.SandboxesApi(signadot_sdk.ApiClient(configuration))
    sandbox_id = None
    preview_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    def setUpClass(cls):
        frontend_fork = signadot_sdk.SandboxFork(
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="frontend",
                namespace="hotrod"
            ),
            customizations=signadot_sdk.SandboxCustomizations(
                images=[
                    signadot_sdk.Image(image="signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0")
                ]
            )
        )
        route_fork = signadot_sdk.SandboxFork(
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="customer",
                namespace="hotrod"
            ),
            customizations=signadot_sdk.SandboxCustomizations(
                images=[
                    signadot_sdk.Image(image="signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0")
                ],
                env=[
                    signadot_sdk.EnvOp(
                        name="FROM_TEST_VAR",
                        valueFrom=signadot_sdk.EnvValueFrom(
                            fork=signadot_sdk.EnvValueFromFork(
                                forkOf=signadot_sdk.ForkOf(
                                    kind="Deployment",
                                    name="frontend",
                                    namespace="hotrod"
                                ),
                                expression="{{ .Service.Host }}:{{ .Service.Port }}"
                            )
                        )
                    )
                ],
                patch=signadot_sdk.CustomPatch(
                    type="strategic",
                    value="""
                    spec:
                      template:
                        spec:
                          containers:
                          - name: hotrod
                            env:
                            - name: PATCH_TEST_VAR
                              value: foo
                    """
                )
            ),
            endpoints=[
                signadot_sdk.ForkEndpoint(
                    name="hotrod-customer",
                    port=8081,
                    protocol="http"
                )
            ]
        )
        request = signadot_sdk.CreateSandboxRequest(
            name="custom-patch-test-{}".format(get_random_string(5)),
            description="Python SDK: sandbox creation with custom patch example",
            cluster=cls.CLUSTER_NAME,
            forks=[route_fork, frontend_fork]
        )

        try:
            api_response = cls.sandboxes_api.create_new_sandbox(cls.ORG_NAME, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        cls.sandbox_id = api_response.sandbox_id

        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-customer", api_response.preview_endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-customer` missing")
        preview_endpoint = filtered_endpoints[0]
        cls.preview_url = preview_endpoint.preview_url

        sandbox_ready = False
        max_attempts = 10
        print("Checking sandbox readiness")
        for i in range(1, max_attempts):
            print("Attempt: {}/{}".format(i, max_attempts))
            sandbox_ready = cls.sandboxes_api.get_sandbox_ready(cls.ORG_NAME, cls.sandbox_id).ready
            if sandbox_ready:
                print("Sandbox is ready!")
                break
            time.sleep(5)

        if not sandbox_ready:
            raise RuntimeError("Sandbox didn't get to Ready state")

    def test_valid_result(self):
        service_url = "{}/customer?customer=392".format(self.preview_url)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["PatchVar"], "foo", "PatchVar must equal foo")
        self.assertIsNotNone(data["FromVar"], "FromVar must not be None")
        self.assertNotEqual(data["FromVar"], "", "FromVar must not be empty")

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox_by_id(cls.ORG_NAME, cls.sandbox_id)

if __name__ == '__main__':
    unittest.main()
