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
const CLUSTER_NAME = process.env.SIGNADOT_CLUSTER_NAME;
const SIGNADOT_ORG = process.env.SIGNADOT_ORG; // Enter your Signadot org name here
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY; // passed from command line
const options = {
    headers: {
        'signadot-api-key': SIGNADOT_API_KEY
    }
};

describe('Create sandbox with custom patch', () => {
    let sandboxesApi, sandboxID;
    before(async () => {
        return new Promise(async (resolve, reject) => {
            try {
                const apiClient = new ApiClient();
                apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
                sandboxesApi = new SandboxesApi(apiClient);

                const sandboxFork = SandboxFork.constructFromObject({
                    forkOf: ForkOf.constructFromObject({
                        kind: 'Deployment',
                        name: 'frontend',
                        namespace: 'hotrod',
                    }),
                    customizations: SandboxCustomizations.constructFromObject({
                        images: [
                            Image.constructFromObject({
                                image: "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0"
                            })
                        ],
                    }),
                });

                const routeFork = SandboxFork.constructFromObject({
                    forkOf: ForkOf.constructFromObject({
                        kind: 'Deployment',
                        name: 'customer',
                        namespace: 'hotrod'
                    }),
                    customizations: SandboxCustomizations.constructFromObject({
                        images: [
                            Image.constructFromObject({
                                image: 'signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0'
                            })
                        ],
                        env: [
                            EnvOp.constructFromObject({
                                name: 'FROM_TEST_VAR',
                                valueFrom: EnvValueFrom.constructFromObject({
                                    forkOf: EnvValueFromFork.constructFromObject({
                                        fork: ForkOf.constructFromObject({
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
                            value: `
                            spec:
                              template:
                                spec:
                                  containers:
                                  - name: hotrod
                                    env:
                                    - name: PATCH_TEST_VAR
                                      value: foo
                            `,
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
                    description: 'created using @signadot/signadot-sdk',
                    cluster: CLUSTER_NAME,
                    forks: [ routeFork, sandboxFork ]
                });

                const response = await sandboxesApi.createNewSandbox(SIGNADOT_ORG, request);
                sandboxID = response.sandboxID;

                const filteredEndpoints = response.previewEndpoints.filter(ep => ep.name === 'hotrod-customer');
                if (filteredEndpoints.length == 0) {
                    throw new Error("Endpoint `hotrod-customer` missing");
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
                expect(data.PatchVar).to.equal("foo")
                expect(data.FromVar).to.not.equal("");
            });
    });

    after(() => {
        return sandboxesApi.deleteSandboxById(SIGNADOT_ORG, sandboxID);
    });
});
