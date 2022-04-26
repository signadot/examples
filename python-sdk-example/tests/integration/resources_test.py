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
    org_name = 'signadot'

    SIGNADOT_API_KEY = os.getenv('SIGNADOT_API_KEY')
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
        customer_service_fork = signadot_sdk.SandboxFork(
            fork_of=signadot_sdk.ForkOf(
                kind="Deployment",
                name="customer",
                namespace="hotrod"
            ),
            customizations=signadot_sdk.SandboxCustomizations(
                images=[signadot_sdk.Image(image="signadot/hotrod:cace2c797082481ac0238cc1310b7816980e3244")],
                env=[
                    signadot_sdk.EnvOp(
                        name="MYSQL_HOST",
                        value_from=signadot_sdk.EnvValueFrom(
                            resource=signadot_sdk.EnvValueFromResource(name="customerdb", output_key="host")
                        )
                    ),
                    signadot_sdk.EnvOp(
                        name="MYSQL_PORT",
                        value_from=signadot_sdk.EnvValueFrom(
                            resource=signadot_sdk.EnvValueFromResource(name="customerdb", output_key="port")
                        )
                    ),
                    signadot_sdk.EnvOp(
                        name="MYSQL_ROOT_PASSWORD",
                        value_from=signadot_sdk.EnvValueFrom(
                            resource=signadot_sdk.EnvValueFromResource(name="customerdb", output_key="root_password")
                        )
                    )
                ]
            ),
            endpoints=[signadot_sdk.ForkEndpoint(name="customer-svc-endpoint", port=8081, protocol="http")]
        )
        request = signadot_sdk.CreateSandboxRequest(
            name="db-resource-test-{}".format(get_random_string(5)),
            description="Python SDK: Create sandbox with ephemeral db resource spun up using hotrod-mariadb plugin",
            cluster="demo",
            resources=[signadot_sdk.SandboxResource(name="customerdb", plugin="hotrod-mariadb", params={"dbname": "customer"})],
            forks=[customer_service_fork]
        )

        try:
            api_response = cls.sandboxes_api.create_new_sandbox(cls.org_name, request)
        except ApiException as e:
            print("Exception creating a sandbox: %s\n" % e)

        cls.sandbox_id = api_response.sandbox_id

        filtered_endpoints = list(filter(lambda ep: ep.name == "customer-svc-endpoint", api_response.preview_endpoints))
        if len(filtered_endpoints) == 0:
            raise RuntimeError("Endpoint `customer-svc-endpoint` missing")
        preview_endpoint = filtered_endpoints[0]
        cls.preview_url = preview_endpoint.preview_url

        sandbox_ready = False
        max_attempts = 10
        print("Checking sandbox readiness")
        for i in range(1, max_attempts):
            print("Attempt: {}/{}".format(i, max_attempts))
            sandbox_ready = cls.sandboxes_api.get_sandbox_ready(cls.org_name, cls.sandbox_id).ready
            if sandbox_ready:
                print("Sandbox is ready!")
                break
            time.sleep(10)

        if not sandbox_ready:
            raise RuntimeError("Sandbox didn't get to Ready state")

    def test_customer_service(self):
        service_url = "{}/customer?customer=999".format(self.preview_url)
        response = requests.get(service_url, headers=self.headers_dict)
        response.raise_for_status()
        data = response.json()

        self.assertEqual(data["ID"], 999)
        self.assertEqual(data["Name"], "Resources Test")
        self.assertEqual(data["Location"], "123,456")

    @classmethod
    def tearDownClass(cls):
        cls.sandboxes_api.delete_sandbox_by_id(cls.org_name, cls.sandbox_id)

if __name__ == '__main__':
    unittest.main()
