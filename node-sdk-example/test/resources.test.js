import {
  ApiClient,
  Sandbox,
  SandboxCustomizations,
  SandboxEnvValueFrom,
  SandboxEnvValueFromResource,
  SandboxEnvVar,
  SandboxesApi,
  SandboxFork,
  SandboxForkEndpoint,
  SandboxForkOf,
  SandboxImage,
  SandboxResource,
  SandboxSpec
} from '@signadot/signadot-sdk';
import axios from 'axios';
import {customAlphabet} from 'nanoid';
import {expect} from 'chai';

const nanoid = customAlphabet('1234567890abcdef', 5);

let endpointURL, sandboxName;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG;
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY;
const SIGNADOT_CLUSTER_NAME = process.env.SIGNADOT_CLUSTER_NAME;
const options = {
  headers: {
    'signadot-api-key': SIGNADOT_API_KEY
  }
};

/*
 * This test creates a Sandbox with below specification:
 *   - Fork HotROD Customer service
 *   - Custom image of HotROD with the Customer Service code updated to include a new customer with:
 *       ID=999, Name="Resources Test" and Location="123,456".
 *   - Create resource using the plugin "hotrod-mariadb"
 *       xref: https://github.com/signadot/hotrod/tree/main/resource-plugins/mariadb
 *       This spins up an ephemeral MariaDB resource that is then used by Customer service to populate customer date.
 *       The request defines the resource and env vars that are populated off of the resource.
 * 
 * Pre-requisites:
 * - hotrod must be installed
 * - resource plugin (hotrod-mariadb) must be installed
 *
 * Once the sandbox is created with the resource, we are testing the customer service endpoint to ensure that the
 * new customer (ID=999) is obtained as expected.
 */
describe('Sandbox test using resources', () => {
  let sandboxesApi;
  before(async () => {
    return new Promise(async (resolve, reject) => {
      try {
        const apiClient = new ApiClient();
        apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
        sandboxesApi = new SandboxesApi(apiClient);

        const customerServiceFork = SandboxFork.constructFromObject({
          forkOf: SandboxForkOf.constructFromObject({
            kind: 'Deployment',
            name: 'customer',
            namespace: 'hotrod'
          }),
          customizations: SandboxCustomizations.constructFromObject({
            images: [
              SandboxImage.constructFromObject({
                image: 'signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd'
              })
            ],
            env: [
              SandboxEnvVar.constructFromObject({
                name: 'MYSQL_HOST',
                valueFrom: SandboxEnvValueFrom.constructFromObject({
                  resource: SandboxEnvValueFromResource.constructFromObject({name: 'customerdb', outputKey: 'host'})
                })
              }),
              SandboxEnvVar.constructFromObject({
                name: 'MYSQL_PORT',
                valueFrom: SandboxEnvValueFrom.constructFromObject({
                  resource: SandboxEnvValueFromResource.constructFromObject({name: 'customerdb', outputKey: 'port'})
                })
              }),
              SandboxEnvVar.constructFromObject({
                name: 'MYSQL_ROOT_PASSWORD',
                valueFrom: SandboxEnvValueFrom.constructFromObject({
                  resource: SandboxEnvValueFromResource.constructFromObject({
                    name: 'customerdb',
                    outputKey: 'root_password'
                  })
                })
              })
            ]
          }),
          endpoints: [
            SandboxForkEndpoint.constructFromObject({
              name: 'customer-svc-endpoint',
              port: 8081,
              protocol: 'http'
            })
          ]
        });

        sandboxName = `db-resource-test-${nanoid()}`;
        const request = Sandbox.constructFromObject({
          spec: SandboxSpec.constructFromObject({
            cluster: SIGNADOT_CLUSTER_NAME,
            description: 'created using @signadot/signadot-sdk',
            forks: [customerServiceFork],
            resources: [
              SandboxResource.constructFromObject({
                name: 'customerdb',
                plugin: 'hotrod-mariadb',
                params: {
                  dbname: 'customer'
                }
              })
            ]
          })
        });

        let sandbox = await sandboxesApi.applySandbox(SIGNADOT_ORG, sandboxName, request);

        const filteredEndpoints = sandbox.endpoints.filter(ep => ep.name === 'customer-svc-endpoint');
        if (filteredEndpoints.length == 0) {
          throw new Error("Endpoint `customer-svc-endpoint` missing");
        }
        endpointURL = filteredEndpoints[0].url;

        const readyStateInterval = setInterval(async () => {
          if (sandbox.status.ready) {
            clearInterval(readyStateInterval);
            resolve();
          }
          sandbox = await sandboxesApi.getSandbox(SIGNADOT_ORG, sandboxName);
        }, 5000);
      } catch (e) {
        reject(e);
      }
    });
  });

  it('Test Customer Service', () => {
    const serviceURL = `${endpointURL}/customer?customer=999`
    axios.get(serviceURL, options)
      .then((response) => {
        expect(response.status).to.equal(200);

        const data = response.data;
        expect(data.ID).to.equal(999);
        expect(data.Name).to.equal("Resources Test");
        expect(data.Location).to.equal("123,456"); // ETA should be positive
      });
  });

  after(() => {
    return sandboxesApi.deleteSandbox(SIGNADOT_ORG, sandboxName);
  });
});
