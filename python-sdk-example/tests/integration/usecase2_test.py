from __future__ import print_function

import time
import unittest
import os
import random
import signadot_sdk
import string
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

To set up for that use-case, we will be creating a workspace with a forks of Frontend and Route services, along with an
endpoint to the frontend service. The Frontend service endpoint/preview URL can then be used to verify the changes
as the workspace preview URL routes the call to the forks of Frontend and Route services instead of the respective
baseline services.

The below code is scoped to creating a workspace with the setup defined above, and printing out the preview endpoint URL
to the frontend service to verify the changes. Using a UI testing setup to test the change on the UI is not covered here.

Sample command to run this test:
cd examples/python-sdk-example
SIGNADOT_API_KEY=<signadot-api-key> ROUTE_IMAGE=signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3 FRONTEND_IMAGE=signadot/hotrod-frontend:5069b62ddc2625244c8504c3bca6602650494879 python3 tests/integration/usecase2_test.py
"""
class TestUseCase2(unittest.TestCase):
    org_name = 'signadot'

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
    if SIGNADOT_API_KEY is None:
        raise OSError("SIGNADOT_API_KEY is not set")

    ROUTE_IMAGE = os.getenv('ROUTE_IMAGE')
    if ROUTE_IMAGE is None:
        raise OSError("ROUTE_IMAGE is not set")

    FRONTEND_IMAGE = os.getenv('FRONTEND_IMAGE')
    if FRONTEND_IMAGE is None:
        raise OSError("FRONTEND_IMAGE is not set")

    configuration = signadot_sdk.Configuration()
    configuration.api_key['signadot-api-key'] = SIGNADOT_API_KEY

    workspaces_api = signadot_sdk.WorkspacesApi(signadot_sdk.ApiClient(configuration))
    workspace_id = None
    preview_url = None
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    @classmethod
    def setUpClass(cls):
        # Define the spec for the fork of route service
        route_fork = signadot_sdk.WorkspaceFork(
            # This tells the application to create a fork of route service/deployment in hotrod namespace.
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="route",
                namespace="hotrod"
            ),
            # Define the various customizations we want to apply on the fork
            customizations=signadot_sdk.WorkspaceCustomizations(
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

        # Define the spec for the fork of frontend service
        frontend_fork = signadot_sdk.WorkspaceFork(
            # This tells the application to create a fork of frontend service/deployment in hotrod namespace.
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="frontend",
                namespace="hotrod"
            ),
            # Define the various customizations we want to apply on the fork
            customizations=signadot_sdk.WorkspaceCustomizations(
                # The image(s) we want to apply on the fork. This assumes that the updated Route service code has been
                # packaged as an image and published to docker.
                # Sample value: signadot/hotrod-frontend:5069b62ddc2625244c8504c3bca6602650494879
                images=[
                    signadot_sdk.Image(image=cls.FRONTEND_IMAGE)
                ],
                # Environment variable changes. Here, we can define new environment variables, or update/delete the
                # ones existing in the baseline deployment.
                env=[
                    signadot_sdk.EnvOp(name="pqr", value="stu", operation="upsert")
                ]
            ),
            # Spec to create an endpoint to fork (of frontend service) serving HTTP traffic on port 8080. This requires
            # a name (valid name can include alphabet, numbers and hyphens, and starts with an alphabet).
            endpoints=[
                signadot_sdk.ForkEndpoint(
                    name="hotrod-frontend",
                    port=8080,
                    protocol="http"
                )
            ]
        )

        # Specification for the workspace. We will pass the spec for the forks of route and frontend services.
        request = signadot_sdk.CreateWorkspaceRequest(
            name="test-ws-{}".format(get_random_string(5)),
            description="Sample workspace created using Python SDK",
            cluster="demo",
            forks=[route_fork, frontend_fork]
        )

        try:
            # API call to create a new workspace
            api_response = cls.workspaces_api.create_new_workspace(cls.org_name, request)
        except ApiException as e:
            print("Exception creating a workspace: %s\n" % e)

        # Workspace ID for the created workspace
        cls.workspace_id = api_response.workspace_id

        filtered_frontend = filterEndpoint(api_response, "hotrod-frontend")
        if len(filtered_frontend) == 0:
            raise RuntimeError("Endpoint `hotrod-frontend` missing")
        frontend_preview_endpoint = filtered_frontend[0]
        cls.preview_url = frontend_preview_endpoint.preview_url
        print("Frontend Service endpoint URL: {}".format(cls.preview_url))

        # Code block to wait until workspace is ready
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

    def test_frontend(self):
        # Run tests on the updated frontend service using the endpoint URL
        pass

    @classmethod
    def tearDownClass(cls):
        # Tear down the workspace
        cls.workspaces_api.delete_workspace_by_id(cls.org_name, cls.workspace_id)


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


def filterEndpoint(api_response, name):
    return list(filter(lambda ep: ep.name == name, api_response.preview_endpoints))


if __name__ == '__main__':
    unittest.main()
