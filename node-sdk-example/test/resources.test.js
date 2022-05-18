import {
  ApiClient,
  CreateSandboxRequest,
  EnvOp, EnvValueFrom, EnvValueFromResource,
  ForkEndpoint,
  ForkOf,
  Image,
  SandboxCustomizations,
  SandboxesApi,
  SandboxFork,
  SandboxResource
} from '@signadot/signadot-sdk';
import axios from 'axios';
import {customAlphabet} from 'nanoid';
import {expect} from 'chai';

const nanoid = customAlphabet('1234567890abcdef', 5);

let previewURL;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG_NAME; 
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
  let sandboxesApi, sandboxID;
  before(async () => {
    return new Promise(async (resolve, reject) => {
      try {
        const apiClient = new ApiClient();
        apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
        sandboxesApi = new SandboxesApi(apiClient);

        const customerServiceFork = SandboxFork.constructFromObject({
          forkOf: ForkOf.constructFromObject({
            kind: 'Deployment',
            name: 'customer',
            namespace: 'hotrod'
          }),
          customizations: SandboxCustomizations.constructFromObject({
            images: [
              Image.constructFromObject({
                image: 'signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd'
              })
            ],
            env: [
              EnvOp.constructFromObject({
                name: 'MYSQL_HOST',
                valueFrom: EnvValueFrom.constructFromObject({
                  resource: EnvValueFromResource.constructFromObject({name: 'customerdb', outputKey: 'host'})
                })
              }),
              EnvOp.constructFromObject({
                name: 'MYSQL_PORT',
                valueFrom: EnvValueFrom.constructFromObject({
                  resource: EnvValueFromResource.constructFromObject({name: 'customerdb', outputKey: 'port'})
                })
              }),
              EnvOp.constructFromObject({
                name: 'MYSQL_ROOT_PASSWORD',
                valueFrom: EnvValueFrom.constructFromObject({
                  resource: EnvValueFromResource.constructFromObject({name: 'customerdb', outputKey: 'root_password'})
                })
              })
            ]
          }),
          endpoints: [
            ForkEndpoint.constructFromObject({
              name: 'customer-svc-endpoint',
              port: 8081,
              protocol: 'http'
            })
          ]
        });

        const request = CreateSandboxRequest.constructFromObject({
          name: `db-resource-test-${nanoid()}`,
          description: 'Node SDK: Create sandbox with ephemeral db resource spun up using hotrod-mariadb plugin',
          cluster: SIGNADOT_CLUSTER_NAME,
          resources: [
            SandboxResource.constructFromObject({
              name: 'customerdb',
              plugin: 'hotrod-mariadb',
              params: {
                dbname: 'customer'
              }
            })
          ],
          forks: [customerServiceFork]
        });

        const response = await sandboxesApi.createNewSandbox(SIGNADOT_ORG, request);
        sandboxID = response.sandboxID;

        const filteredEndpoints = response.previewEndpoints.filter(ep => ep.name === 'customer-svc-endpoint');
        if (filteredEndpoints.length == 0) {
          throw new Error("Endpoint `customer-svc-endpoint` missing");
        }
        previewURL = filteredEndpoints[0].previewURL;

        const readyStateInterval = setInterval(async () => {
          const readyState = await sandboxesApi.getSandboxReady(SIGNADOT_ORG, sandboxID);
          if (readyState.ready) {
            clearInterval(readyStateInterval);
            resolve();
          }
        }, 5000);
      } catch (e) {
        reject(e);
      }
    });
  });

  it('Test Customer Service', () => {
    const serviceURL = `${previewURL}/customer?customer=999`
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
    return sandboxesApi.deleteSandboxById(SIGNADOT_ORG, sandboxID);
  });
});
