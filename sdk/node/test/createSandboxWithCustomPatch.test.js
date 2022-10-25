import {
  ApiClient,
  Sandbox,
  SandboxCustomizations,
  SandboxCustomPatch,
  SandboxesApi,
  SandboxFork,
  SandboxForkEndpoint,
  SandboxForkOf,
  SandboxImage,
  SandboxSpec,
  SandboxTTL
} from '@signadot/signadot-sdk';
import axios from 'axios';
import {customAlphabet} from 'nanoid';
import {expect} from 'chai';

const nanoid = customAlphabet('1234567890abcdef', 5);

let endpointURL, sandboxName;
const HOTROD_TEST_IMAGE = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0";

const SIGNADOT_CLUSTER_NAME = process.env.SIGNADOT_CLUSTER_NAME;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG;
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY; // passed from command line
const options = {
  headers: {
    'signadot-api-key': SIGNADOT_API_KEY
  }
};

describe('Create sandbox with custom patch', () => {
  let sandboxesApi, envVarValue, customPatch;
  before(async () => {
    return new Promise(async (resolve, reject) => {
      try {
        const apiClient = new ApiClient();
        apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
        sandboxesApi = new SandboxesApi(apiClient);

        envVarValue = nanoid();
        customPatch = `
spec:
  template:
    spec:
      containers:
      - name: hotrod
        env:
        - name: PATCH_TEST_VAR
          value: ${envVarValue}`;

        const customerFork = SandboxFork.constructFromObject({
          forkOf: SandboxForkOf.constructFromObject({
            kind: 'Deployment',
            name: 'customer',
            namespace: 'hotrod'
          }),
          customizations: SandboxCustomizations.constructFromObject({
            images: [
              SandboxImage.constructFromObject({
                image: HOTROD_TEST_IMAGE
              })
            ],
            patch: SandboxCustomPatch.constructFromObject({
              type: 'strategic',
              value: customPatch,
            }),
          }),
          endpoints: [
            SandboxForkEndpoint.constructFromObject({
              name: 'hotrod-customer',
              port: 8081,
              protocol: 'http'
            })
          ]
        });

        sandboxName = `customer-patch-test-${nanoid()}`;
        const request = Sandbox.constructFromObject({
          spec: SandboxSpec.constructFromObject({
            cluster: SIGNADOT_CLUSTER_NAME,
            ttl: SandboxTTL.constructFromObject({ duration: "10m" }),
            description: 'created using @signadot/signadot-sdk',
            forks: [customerFork]
          })
        });

        let sandbox = await sandboxesApi.applySandbox(SIGNADOT_ORG, sandboxName, request);
        const filteredEndpoints = sandbox.endpoints.filter(ep => ep.name === 'hotrod-customer');
        if (filteredEndpoints.length === 0) {
          reject(new Error("Endpoint `hotrod-customer` missing"));
          return;
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

  it('Customer service env vars', () => {
    const serviceURL = `${endpointURL}/customer?customer=392`
    axios.get(serviceURL, options)
      .then((response) => {
        expect(response.status).to.equal(200);

        const data = response.data;
        ['PatchVar'].forEach(x => expect(data).to.have.property(x));
        expect(data.PatchVar).to.equal(envVarValue)
      });
  });

  after(() => {
    return sandboxesApi.deleteSandbox(SIGNADOT_ORG, sandboxName);
  });
});
