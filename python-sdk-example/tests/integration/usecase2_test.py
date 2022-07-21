from __future__ import print_function

import os
import random
import string
import time
import unittest

import timeout_decorator
from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, SandboxForkEndpoint, SandboxEnvVar, Sandbox, SandboxSpec
from signadot_sdk.rest import ApiException

"""
Use Case 2
==========
In this use-case, we have a multi-service setup consisting of Svc-A and Svc-B wherein Svc-B is running behind Svc-A. We
want to test a scenario wherein both Svc-A and Svc-B have changes, and we want to access the endpoint to the updated
Svc-A and use it to test/verify the changes to both Svc-A and Svc-B. In the context of the [HotRod](https://github.com/signadot/hotrod)
application, consider Svc-A and Svc-B to be `Frontend` and `Route` services respectively.

Original Flow:
------> [Svc-A] ------> [[sidecar] Svc-B]

Preview Flow:
                      *---> [[sidecar] ... ]
                     /         \
---> [forkOf Svc-A] *           *---> [forkOf Svc-B]

To set up for that use-case, we will be creating a sandbox with a forks of Frontend and Route services, along with an
endpoint to the frontend service. The Frontend service endpoint URL can then be used to verify the changes
as the sandbox endpoint URL routes the call to the forks of Frontend and Route services instead of the respective
baseline services.

The below code is scoped to creating a sandbox with the setup defined above, and printing out the endpoint URL
to the frontend service to verify the changes. Using a UI testing setup to test the change on the UI is not covered here.

Sample command to run this test:
cd examples/python-sdk-example
SIGNADOT_API_KEY=<signadot-api-key> ROUTE_IMAGE=signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3 FRONTEND_IMAGE=signadot/hotrod-frontend:5069b62ddc2625244c8504c3bca6602650494879 python3 tests/integration/usecase2_test.py
"""
class TestUseCase2(unittest.TestCase):
    SIGNADOT_CLUSTER_NAME = os.getenv('SIGNADOT_CLUSTER_NAME')
    if SIGNADOT_CLUSTER_NAME is None:
        raise OSError("SIGNADOT_CLUSTER_NAME is not set")

    SIGNADOT_ORG = os.getenv('SIGNADOT_ORG')
    if SIGNADOT_ORG is None:
        raise OSError("SIGNADOT_ORG is not set")

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    ROUTE_IMAGE = os.getenv('ROUTE_IMAGE')
    if ROUTE_IMAGE is None:
        raise OSError("ROUTE_IMAGE is not set")

    FRONTEND_IMAGE = os.getenv('FRONTEND_IMAGE')
    if FRONTEND_IMAGE is None:
        raise OSError("FRONTEND_IMAGE is not set")

    configuration = Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    sandboxes_api = SandboxesApi(ApiClient(configuration))
    sandbox_name = None
    endpoint_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    @timeout_decorator.timeout(120)
    def setUpClass(cls):
        # Define the spec for the fork of route service
        route_fork = SandboxFork(
            # This tells the application to create a fork of route service/deployment in hotrod namespace.
            fork_of=SandboxForkOf(
                kind="Deployment",
                name="route",
                namespace="hotrod"
            ),
            # Define the various customizations we want to apply on the fork
            customizations=SandboxCustomizations(
                # The image(s) we want to apply on the fork. This assumes that the updated Route service code has been
                # packaged as an image and published to docker.
                # Sample value: signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3
                images=[
                    SandboxImage(image=cls.ROUTE_IMAGE)
                ],
                # Environment variable changes. Here, we can define new environment variables, or update/delete the
                # ones existing in the baseline deployment.
                env=[
                    SandboxEnvVar(name="abc", value="xyz")
                ]
            ),
            # Since we are only interested in previewing the change to the Route service through the frontend, we do not
            # need an endpoint to the fork-of Route service.
            endpoints=None
        )

        # Define the spec for the fork of frontend service
        frontend_fork = SandboxFork(
            # This tells the application to create a fork of frontend service/deployment in hotrod namespace.
            fork_of=SandboxForkOf(
                kind="Deployment",
                name="frontend",
                namespace="hotrod"
            ),
            # Define the various customizations we want to apply on the fork
            customizations=SandboxCustomizations(
                # The image(s) we want to apply on the fork. This assumes that the updated Route service code has been
                # packaged as an image and published to docker.
                # Sample value: signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd
                images=[
                    SandboxImage(image=cls.FRONTEND_IMAGE)
                ],
                # Environment variable changes. Here, we can define new environment variables, or update/delete the
                # ones existing in the baseline deployment.
                env=[
                    SandboxEnvVar(name="pqr", value="stu")
                ]
            ),
            # Spec to create an endpoint to fork (of frontend service) serving HTTP traffic on port 8080. This requires
            # a name (valid name can include alphabet, numbers and hyphens, and starts with an alphabet).
            endpoints=[
                SandboxForkEndpoint(
                    name="hotrod-frontend",
                    port=8080,
                    protocol="http"
                )
            ]
        )

        cls.sandbox_name = "test-ws-{}".format(get_random_string(5))
        # Specification for the sandbox. We will pass the spec for the forks of route and frontend services.
        request = Sandbox(
            spec=SandboxSpec(
                description="Sample sandbox created using Python SDK",
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                forks=[route_fork, frontend_fork]
            )
        )

        try:
            # API call to create a new sandbox
            sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-frontend", sandbox.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-frontend` missing")
        cls.endpoint_url = filtered_endpoints[0].url
        print("Frontend Service endpoint URL: {}".format(cls.endpoint_url))

        # Code block to wait until sandbox is ready
        sandbox_ready = False
        max_attempts = 20
        print("Checking sandbox readiness")
        for i in range(1, max_attempts):
            print("Attempt: {}/{}".format(i, max_attempts))
            if sandbox.status.ready:
                sandbox_ready = True
                print("Sandbox is ready!")
                break
            time.sleep(5)
            sandbox = cls.sandboxes_api.get_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)

        if not sandbox_ready:
            raise RuntimeError("Sandbox didn't get to Ready state")

    def test_frontend(self):
        # Run tests on the updated frontend service using the endpoint URL
        pass

    @classmethod
    def tearDownClass(cls):
        # Tear down the sandbox
        cls.sandboxes_api.delete_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


if __name__ == '__main__':
    unittest.main()
