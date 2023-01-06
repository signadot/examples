from __future__ import print_function

import os
import random
import string
import time
import unittest

import timeout_decorator
from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, SandboxEnvVar, Sandbox, SandboxSpec, SandboxHostEndpoint, SandboxTTL, \
    SandboxDefaultRouteGroup, RouteGroupSpecEndpoint
from signadot_sdk.rest import ApiException

"""
Use Case 1
==========
In this use-case, we have a multi-service setup consisting of Svc-A and Svc-B wherein Svc-B is running behind Svc-A. We
want to test a scenario wherein Svc-B has some changes, and we want to verify that the changes are reflected in the
call to Svc-A. In the context of the [HotRod](https://github.com/signadot/hotrod) application, consider Svc-A and Svc-B
to be `Frontend` and `Route` services respectively.
 
Original Flow:
---> [Svc-A] ---> [[sidecar] Svc-B]

Preview Flow:
---> [Svc-A] ---> [[sidecar] ... ]
                      \
                       *---> [forkOf Svc-B]

To set up for that use-case, we will be creating a sandbox with a fork of the Route service, along with an endpoint to
the frontend service. The Frontend service endpoint URL can then be used to verify that the changes as the sandboxes
routes the call to the fork of Route service instead of the baseline Route service.

The below code is scoped to creating a sandbox with the above setup, and printing out the endpoint URL to
the frontend service to verify the change. Using a UI testing setup to test out the change on the UI is not covered here.

Sample command to run this test:
cd examples/python-sdk-example
SIGNADOT_API_KEY=<signadot-api-key> ROUTE_IMAGE=signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd python3 tests/integration/usecase1_test.py
"""


class TestUseCase1(unittest.TestCase):
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
                # Sample value: signadot/hotrod:latest
                images=[
                    SandboxImage(image=cls.ROUTE_IMAGE)
                ],
                # Environment variable changes. Here, we can define new environment variables, or update/delete the
                # ones existing in the baseline deployment.
                env=[
                    SandboxEnvVar(name="abc", value="xyz")
                ]
            )
        )

        cls.sandbox_name = "test-ws-{}".format(get_random_string(5))
        # Specification for the sandbox. We will pass the spec for the fork of route service and the additional
        # endpoint to frontend service.
        request = Sandbox(
            spec=SandboxSpec(
                description="Sample sandbox created using Python SDK (use case 1)",
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                ttl=SandboxTTL(duration="10m"),
                forks=[route_fork],
                default_route_group=SandboxDefaultRouteGroup(
                    endpoints=[
                        RouteGroupSpecEndpoint(name="hotrod-frontend", target="http://frontend.hotrod.svc:8080")
                    ]
                )
            )
        )

        try:
            # API call to create a new sandbox
            sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        # Filtering out the endpoint to the frontend service by name.
        filtered_endpoints = list(filter(lambda ep: ep.name == "hotrod-frontend", sandbox.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `hotrod-frontend` missing")
        cls.endpoint_url = filtered_endpoints[0].url
        print("Frontend Service endpoint URL: {}".format(cls.endpoint_url))

        # Code block to wait until sandbox is ready
        while not sandbox.status.ready:
            time.sleep(5)
            sandbox = cls.sandboxes_api.get_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)

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
