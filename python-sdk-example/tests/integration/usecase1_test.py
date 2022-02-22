from __future__ import print_function

import time
import unittest
import os
import random
import signadot_sdk
import string
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

The below code is scoped to creating a sandbox with the above setup, and printing out the preview endpoint URL to
the frontend service to verify the change. Using a UI testing setup to test out the change on the UI is not covered here.

Sample command to run this test:
cd examples/python-sdk-example
SIGNADOT_API_KEY=<signadot-api-key> ROUTE_IMAGE=signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3 python3 tests/integration/usecase1_test.py
"""
class TestUseCase1(unittest.TestCase):
    org_name = 'signadot'

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    ROUTE_IMAGE = os.getenv('ROUTE_IMAGE')
    if ROUTE_IMAGE is None:
        raise OSError("ROUTE_IMAGE is not set")

    configuration = signadot_sdk.Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    sandboxes_api = signadot_sdk.SandboxesApi(signadot_sdk.ApiClient(configuration))
    sandbox_id = None
    preview_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    def setUpClass(cls):
        # Define the spec for the fork of route service
        route_fork = signadot_sdk.SandboxFork(
            # This tells the application to create a fork of route service/deployment in hotrod namespace.
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="route",
                namespace="hotrod"
            ),
            # Define the various customizations we want to apply on the fork
            customizations=signadot_sdk.SandboxCustomizations(
                # The image(s) we want to apply on the fork. This assumes that the updated Route service code has been
                # packaged as an image and published to docker.
                # Sample value: signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3
                images=[
                    signadot_sdk.Image(image=cls.ROUTE_IMAGE)
                ],
                # Environment variable changes. Here, we can define new environment variables, or update/delete the
                # ones existing in the baseline deployment.
                env=[
                    signadot_sdk.EnvOp(name="abc", value="xyz", operation="upsert")
                ]
            ),
            # Since we are only interested in previewing the change to the Route service through the frontend, we do not
            # need an endpoint to the fork-of Route service.
            endpoints=None
        )

        # Define an additional endpoint to the frontend service as we're interested in testing the Route service
        # changes through the frontend service.
        frontend_endpoint = signadot_sdk.SandboxEndpoint(
            host="frontend.hotrod.svc",  # Host for frontend service
            name="hotrod-frontend",  # Name for the endpoint
            port=8080,  # Frontend service operates on port 8080
            protocol="http"  # Frontend service uses HTTP protocol
        )

        # Specification for the sandbox. We will pass the spec for the fork of route service and the additional
        # endpoint to frontend service.
        request = signadot_sdk.CreateSandboxRequest(
            name="test-ws-{}".format(get_random_string(5)),
            description="Sample sandbox created using Python SDK",
            cluster="demo",
            forks=[route_fork],
            endpoints=[frontend_endpoint]
        )

        try:
            # API call to create a new sandbox
            api_response = cls.sandboxes_api.create_new_sandbox(cls.org_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        # Sandbox ID for the created sandbox
        cls.sandbox_id = api_response.sandbox_id

        # Filtering out the endpoint to the frontend service by name.
        filtered_frontend = filter_endpoint(api_response, "hotrod-frontend")
        if len(filtered_frontend) == 0:
            raise RuntimeError("Endpoint `hotrod-frontend` missing")
        frontend_preview_endpoint = filtered_frontend[0]
        cls.preview_url = frontend_preview_endpoint.preview_url
        print("Frontend Service endpoint URL: {}".format(cls.preview_url))

        # Code block to wait until sandbox is ready
        sandbox_ready = False
        max_attempts = 10
        print("Checking sandbox readiness")
        for i in range(1, max_attempts):
            print("Attempt: {}/{}".format(i, max_attempts))
            sandbox_ready = cls.sandboxes_api.get_sandbox_ready(cls.org_name, cls.sandbox_id).ready
            if sandbox_ready:
                print("Sandbox is ready!")
                break
            time.sleep(5)

        if not sandbox_ready:
            raise RuntimeError("Sandbox didn't get to Ready state")

    def test_frontend(self):
        # Run tests on the updated frontend service using the endpoint URL
        pass

    @classmethod
    def tearDownClass(cls):
        # Tear down the sandbox
        cls.sandboxes_api.delete_sandbox_by_id(cls.org_name, cls.sandbox_id)


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


def filter_endpoint(api_response, name):
    return list(filter(lambda ep: ep.name == name, api_response.preview_endpoints))


if __name__ == '__main__':
    unittest.main()
