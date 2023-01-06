from __future__ import print_function

import os
import random
import string
import time
import unittest

import requests
import timeout_decorator
from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, Sandbox, SandboxSpec, SandboxTTL, \
    RouteGroupSpecEndpoint, RouteGroup, RouteGroupSpec, RouteGroupMatch, RouteGroupMatchLabel, \
    RouteGroupsApi


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


"""
This test creates a sandbox, and a routegroup matching the sandbox by labels, and verifies that the routegroup
endpoint reflects the changes introduced by the sandbox.

Sandbox:
The sandbox spec contains the below customization:
- forks the frontend service, applying the image - `signadot/hotrod-e2e:latest`. This includes the frontend service
   change to return the text 'Hot R.O.D. (e2e-test)'.
- Applies the label: `feature: <random value>`

Routegroup:
The routegroup spec contains the below customization:
- rule to match by label: `feature: <random value from the sandbox spec above>`
- endpoint to frontend service (target: http://frontend.hotrod.svc:8080)

Test:
We consume the routegroup endpoint (to the frontend service), and verify that the response (HTML) contains the
text 'Hot R.O.D. (e2e-test)'.
"""


class TestRouteGroups(unittest.TestCase):
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

    api_client = ApiClient(configuration)
    sandboxes_api = SandboxesApi(api_client)
    routegroups_api = RouteGroupsApi(api_client)
    headers_dict = {"signadot-api-key": SIGNADOT_API_KEY}

    sandbox = None
    routegroup = None

    @classmethod
    @timeout_decorator.timeout(120)
    def setUpClass(cls):
        labelKey = "feature"
        labelValue = get_random_string(5)
        cls.sandbox = cls.createSandbox(labelKey, labelValue)
        cls.routegroup = cls.createRouteGroup(labelKey, labelValue)

        filtered_endpoints = list(filter(lambda ep: ep.name == "frontend-ep", cls.routegroup.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `frontend-ep` missing in routegroup")
        cls.endpoint_url = filtered_endpoints[0].url

    @classmethod
    def createSandbox(cls, labelKey, labelValue):
        frontend_fork = SandboxFork(
            fork_of=SandboxForkOf(kind="Deployment", name="frontend", namespace="hotrod"),
            customizations=SandboxCustomizations(images=[SandboxImage(image="signadot/hotrod-e2e:latest")]))

        sandbox_name = "rg-test-{}".format(get_random_string(5))
        request = Sandbox(
            spec=SandboxSpec(
                labels={labelKey: labelValue},
                description="Created using Python SDK to test RouteGroups",
                ttl=SandboxTTL(duration="10m"),
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                forks=[frontend_fork]))

        sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, sandbox_name, request)

        # Code block to wait until sandbox is ready
        while not sandbox.status.ready:
            time.sleep(5)
            sandbox = cls.sandboxes_api.get_sandbox(cls.SIGNADOT_ORG, sandbox_name)
        return sandbox

    @classmethod
    def createRouteGroup(cls, labelKey, labelValue):
        routegroup_name = "test-rg-{}".format(get_random_string(5))
        request = RouteGroup(
            spec=RouteGroupSpec(
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                description="Created using Python SDK to test RouteGroups",
                match=RouteGroupMatch(label=RouteGroupMatchLabel(key=labelKey, value=labelValue)),
                endpoints=[RouteGroupSpecEndpoint(name="frontend-ep", target="http://frontend.hotrod.svc:8080")]))

        routegroup = cls.routegroups_api.apply_routegroup(cls.SIGNADOT_ORG, routegroup_name, request)

        # Code block to wait until routegroup is ready
        while not routegroup.status.ready:
            time.sleep(5)
            routegroup = cls.routegroups_api.get_routegroup(cls.SIGNADOT_ORG, routegroup_name)
        return routegroup

    def test_frontend_change(self):
        response = requests.get(self.endpoint_url, headers=self.headers_dict)
        response.raise_for_status()
        html = response.content.decode("utf-8")

        expected_content = "Hot R.O.D. (e2e-test)"
        self.assertTrue(expected_content in html)

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox(cls.SIGNADOT_ORG, cls.sandbox.name)
        cls.routegroups_api.delete_routegroup(cls.SIGNADOT_ORG, cls.routegroup.name)


if __name__ == '__main__':
    unittest.main()
