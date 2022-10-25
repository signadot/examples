import {
  ApiClient,
  Sandbox,
  SandboxCustomizations,
  SandboxEnvVar,
  SandboxesApi,
  SandboxFork,
  SandboxForkEndpoint,
  SandboxForkOf,
  SandboxImage,
  SandboxSpec,
  SandboxTTL,
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

describe('Test a service using sandbox', () => {
  let sandboxesApi;
  before(async () => {
    return new Promise(async (resolve, reject) => {
      try {
        const apiClient = new ApiClient();
        apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
        sandboxesApi = new SandboxesApi(apiClient);

        const routeFork = SandboxFork.constructFromObject({
          forkOf: SandboxForkOf.constructFromObject({
            kind: 'Deployment',
            name: 'route',
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
                name: 'abc',
                value: 'def'
              })
            ],
          }),
          endpoints: [
            SandboxForkEndpoint.constructFromObject({
              name: 'hotrod-route',
              protocol: 'http'
            })
          ]
        });

        sandboxName = `test-ws-${nanoid()}`;
        const request = Sandbox.constructFromObject({
          spec: SandboxSpec.constructFromObject({
            labels: {key1: "value1", key2: "value2"},
            cluster: SIGNADOT_CLUSTER_NAME,
            ttl: SandboxTTL.constructFromObject({ duration: "10m" }),
            description: 'created using @signadot/signadot-sdk',
            forks: [routeFork]
          })
        });

        let sandbox = await sandboxesApi.applySandbox(SIGNADOT_ORG, sandboxName, request);

        const filteredEndpoints = sandbox.endpoints.filter(ep => ep.name === 'hotrod-route');
        if (filteredEndpoints.length == 0) {
          throw new Error("Endpoint `hotrod-route` missing");
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

  it('Route service test', () => {
    const serviceURL = `${endpointURL}/route?pickup=123&dropoff=456`
    axios.get(serviceURL, options)
      .then((response) => {
        expect(response.status).to.equal(200);

        const data = response.data;
        ['Pickup', 'Dropoff', 'ETA'].forEach(x => expect(data).to.have.property(x));
        expect(data.Pickup).to.equal("123");
        expect(data.DropOff).to.equal("456");
        expect(data.ETA).isAbove(0); // ETA should be positive
      });
  });

  after(() => {
    return sandboxesApi.deleteSandbox(SIGNADOT_ORG, sandboxName);
  });
});
