from __future__ import print_function

import os
import random
import string
import time
import unittest

import requests
import timeout_decorator
from signadot_sdk import Configuration, SandboxesApi, ApiClient, SandboxFork, SandboxForkOf, \
    SandboxCustomizations, SandboxImage, SandboxForkEndpoint, SandboxEnvVar, Sandbox, SandboxSpec, SandboxEnvValueFrom, \
    SandboxEnvValueFromResource, SandboxResource
from signadot_sdk.rest import ApiException


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(length))


# This test creates a Sandbox with below specification:
#   - Fork HotROD Customer service
#   - Custom image of HotROD with the Customer Service code updated to include a new customer with:
#       ID=999, Name="Resources Test" and Location="123,456".
#   - Create resource using the plugin "hotrod-mariadb"
#       xref: https://github.com/signadot/hotrod/tree/main/resource-plugins/mariadb
#       This spins up an ephemeral MariaDB resource that is then used by Customer service to populate customer date.
#       The request defines the resource and env vars that are populated off of the resource.
# 
# Pre-requisites:
# - hotrod must be installed
# - resource plugin (hotrod-mariadb) must be installed
#
# Once the sandbox is created with the resource, we are testing the customer service endpoint to ensure that the
# new customer (ID=999) is obtained as expected.
class TestWithResources(unittest.TestCase):
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
        customer_service_fork = SandboxFork(
            fork_of=SandboxForkOf(
                kind="Deployment",
                name="customer",
                namespace="hotrod"
            ),
            customizations=SandboxCustomizations(
                images=[SandboxImage(image="signadot/hotrod:cace2c797082481ac0238cc1310b7816980e3244")],
                env=[
                    SandboxEnvVar(
                        name="MYSQL_HOST",
                        value_from=SandboxEnvValueFrom(
                            resource=SandboxEnvValueFromResource(name="customerdb", output_key="host")
                        )
                    ),
                    SandboxEnvVar(
                        name="MYSQL_PORT",
                        value_from=SandboxEnvValueFrom(
                            resource=SandboxEnvValueFromResource(name="customerdb", output_key="port")
                        )
                    ),
                    SandboxEnvVar(
                        name="MYSQL_ROOT_PASSWORD",
                        value_from=SandboxEnvValueFrom(
                            resource=SandboxEnvValueFromResource(name="customerdb", output_key="root_password")
                        )
                    )
                ]
            ),
            endpoints=[SandboxForkEndpoint(name="customer-svc-endpoint", port=8081, protocol="http")]
        )

        cls.sandbox_name = "db-resource-test-{}".format(get_random_string(5))
        request = Sandbox(
            spec=SandboxSpec(
                description="Python SDK: Create sandbox with ephemeral db resource spun up using hotrod-mariadb plugin",
                cluster=cls.SIGNADOT_CLUSTER_NAME,
                resources=[SandboxResource(name="customerdb", plugin="hotrod-mariadb",
                                           params={"dbname": "customer"})],
                forks=[customer_service_fork]
            )
        )

        try:
            sandbox = cls.sandboxes_api.apply_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        filtered_endpoints = list(filter(lambda ep: ep.name == "customer-svc-endpoint", sandbox.endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `customer-svc-endpoint` missing")
        cls.endpoint_url = filtered_endpoints[0].url

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

    def test_customer_service(self):
        service_url = "{}/customer?customer=999".format(self.endpoint_url)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["ID"], 999)
        self.assertEqual(data["Name"], "Resources Test")
        self.assertEqual(data["Location"], "123,456")

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox(cls.SIGNADOT_ORG, cls.sandbox_name)


if __name__ == '__main__':
    unittest.main()
