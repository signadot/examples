import {
  ApiClient,
  Sandbox,
  SandboxCustomizations,
  SandboxEnvValueFrom,
  SandboxEnvValueFromFork,
  SandboxEnvVar,
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

let endpointURL;

const HOTROD_TEST_IMAGE = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0";

const SIGNADOT_CLUSTER_NAME = process.env.SIGNADOT_CLUSTER_NAME;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG;
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY; // passed from command line
const options = {
  headers: {
    'signadot-api-key': SIGNADOT_API_KEY
  }
};

describe('Create sandbox with xref', () => {
  let sandboxesApi, sandboxName;
  before(async () => {
    return new Promise(async (resolve, reject) => {
      try {
        const apiClient = new ApiClient();
        apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
        sandboxesApi = new SandboxesApi(apiClient);

        const frontendFork = SandboxFork.constructFromObject({
          forkOf: SandboxForkOf.constructFromObject({
            kind: 'Deployment',
            name: 'frontend',
            namespace: 'hotrod',
          }),
          customizations: SandboxCustomizations.constructFromObject({
            images: [
              SandboxImage.constructFromObject({
                image: HOTROD_TEST_IMAGE
              })
            ],
          }),
        });

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
            env: [
              SandboxEnvVar.constructFromObject({
                name: 'FROM_TEST_VAR',
                valueFrom: SandboxEnvValueFrom.constructFromObject({
                  fork: SandboxEnvValueFromFork.constructFromObject({
                    forkOf: SandboxForkOf.constructFromObject({
                      kind: 'Deployment',
                      namespace: 'hotrod',
                      name: 'frontend'
                    }),
                    expression: '{{ .Service.Host }}:{{ .Service.Port }}',
                  })
                }),
              })
            ],
          }),
          endpoints: [
            SandboxForkEndpoint.constructFromObject({
              name: 'hotrod-customer',
              port: 8081,
              protocol: 'http'
            })
          ]
        });

        sandboxName = `xref-test-${nanoid()}`;
        const request = Sandbox.constructFromObject({
          spec: SandboxSpec.constructFromObject({
            cluster: SIGNADOT_CLUSTER_NAME,
            ttl: SandboxTTL.constructFromObject({ duration: "10m" }),
            description: 'Node SDK: sandbox creation with xref example',
            forks: [customerFork, frontendFork]
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
        ['FromVar'].forEach(x => expect(data).to.have.property(x));
        expect(data.FromVar).to.not.equal("");
      });
  });

  after(() => {
    return sandboxesApi.deleteSandbox(SIGNADOT_ORG, sandboxName);
  });
});
