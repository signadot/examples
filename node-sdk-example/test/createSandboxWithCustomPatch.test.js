import {
    ApiClient,
    CreateSandboxRequest,
    CustomPatch,
    EnvOp,
    EnvValueFrom,
    EnvValueFromFork,
    ForkEndpoint,
    ForkOf,
    Image,
    SandboxCustomizations,
    SandboxFork,
    SandboxesApi
} from '@signadot/signadot-sdk';
import axios from 'axios';
import {customAlphabet} from 'nanoid';
import {expect} from 'chai';

const nanoid = customAlphabet('1234567890abcdef', 5);

let previewURL;

const IMAGE_PATCH = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0";

const CLUSTER_NAME = process.env.SIGNADOT_CLUSTER_NAME;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG;
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY; // passed from command line
const options = {
    headers: {
        'signadot-api-key': SIGNADOT_API_KEY
    }
};

describe('Create sandbox with custom patch', () => {
    let sandboxesApi, sandboxID, envVarValue, customPatch;
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

                const sandboxFork = SandboxFork.constructFromObject({
                    forkOf: ForkOf.constructFromObject({
                        kind: 'Deployment',
                        name: 'frontend',
                        namespace: 'hotrod',
                    }),
                    customizations: SandboxCustomizations.constructFromObject({
                        images: [
                            Image.constructFromObject({
                                image: IMAGE_PATCH
                            })
                        ],
                    }),
                });

                const customerFork = SandboxFork.constructFromObject({
                    forkOf: ForkOf.constructFromObject({
                        kind: 'Deployment',
                        name: 'customer',
                        namespace: 'hotrod'
                    }),
                    customizations: SandboxCustomizations.constructFromObject({
                        images: [
                            Image.constructFromObject({
                                image: IMAGE_PATCH
                            })
                        ],
                        env: [
                            EnvOp.constructFromObject({
                                name: 'FROM_TEST_VAR',
                                valueFrom: EnvValueFrom.constructFromObject({
                                    fork: EnvValueFromFork.constructFromObject({
                                        forkOf: ForkOf.constructFromObject({
                                            kind: 'Deployment',
                                            namespace: 'hotrod',
                                            name: 'frontend'
                                        }),
                                        expression: '{{ .Service.Host }}:{{ .Service.Port }}',
                                    })
                                }),
                            })
                        ],
                        patch: CustomPatch.constructFromObject({
                            type: 'strategic',
                            value: customPatch,
                        }),
                    }),
                    endpoints: [
                        ForkEndpoint.constructFromObject({
                            name: 'hotrod-customer',
                            port: 8081,
                            protocol: 'http'
                        })
                    ]
                });

                const request = CreateSandboxRequest.constructFromObject({
                    name: `customer-patch-test-${nanoid()}`,
                    description: 'Node SDK: sandbox creation with custom patch example',
                    cluster: CLUSTER_NAME,
                    forks: [ customerFork, sandboxFork ]
                });

                const response = await sandboxesApi.createNewSandbox(SIGNADOT_ORG, request);
                sandboxID = response.sandboxID;

                const filteredEndpoints = response.previewEndpoints.filter(ep => ep.name === 'hotrod-customer');
                if (filteredEndpoints.length === 0) {
                    reject(new Error("Endpoint `hotrod-customer` missing"));
                    return;
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

    it('Customer service env vars', () => {
        const serviceURL = `${previewURL}/customer?customer=392`
        axios.get(serviceURL, options)
            .then((response) => {
                expect(response.status).to.equal(200);

                const data = response.data;
                ['PatchVar', 'FromVar'].forEach(x => expect(data).to.have.property(x));
                expect(data.PatchVar).to.equal(envVarValue)
                expect(data.FromVar).to.not.equal("");
            });
    });

    after(() => {
        return sandboxesApi.deleteSandboxById(SIGNADOT_ORG, sandboxID);
    });
});
