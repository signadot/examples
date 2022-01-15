import {
    ApiClient,
    CreateWorkspaceRequest,
    EnvOp,
    ForkEndpoint,
    ForkOf,
    Image,
    WorkspaceCustomizations,
    WorkspaceFork,
    WorkspacesApi
} from '@signadot/signadot-sdk';
import axios from 'axios';
import {customAlphabet} from 'nanoid';
import {expect} from 'chai';

const nanoid = customAlphabet('1234567890abcdef', 5);

let previewURL;
const SIGNADOT_ORG = 'signadot'; // Enter your Signadot org name here
const SIGNADOT_API_KEY = process.env.SIGNADOT_API_KEY; // passed from command line

describe('Test Signadot SDK', () => {
    let workspacesApi, workspaceID;
    before(async () => {
        return new Promise(async (resolve, reject) => {
            try {
                const apiClient = new ApiClient();
                apiClient.authentications.ApiKeyAuth.apiKey = SIGNADOT_API_KEY;
                workspacesApi = new WorkspacesApi(apiClient);

                const routeFork = WorkspaceFork.constructFromObject({
                    forkOf: ForkOf.constructFromObject({
                        kind: 'Deployment',
                        name: 'route',
                        namespace: 'hotrod'
                    }),
                    customizations: WorkspaceCustomizations.constructFromObject({
                        images: [
                            Image.constructFromObject({
                                image: 'signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3'
                            })
                        ],
                        env: [
                            EnvOp.constructFromObject({
                                name: 'abc',
                                value: 'def'
                            })
                        ]
                    }),
                    endpoints: [
                        ForkEndpoint.constructFromObject({
                            name: 'hotrod-route',
                            port: 8083,
                            protocol: 'http'
                        })
                    ]
                });

                const request = CreateWorkspaceRequest.constructFromObject({
                    name: `test-ws-${nanoid()}`,
                    description: 'created using @signadot/signadot-sdk',
                    cluster: 'demo',
                    namespace: 'hotrod',
                    forks: [ routeFork ]
                });

                const response = await workspacesApi.createNewWorkspace(SIGNADOT_ORG, request);
                workspaceID = response.workspaceID;

                const filteredEndpoints = response.previewEndpoints.filter(ep => ep.name === 'hotrod-route');
                if (filteredEndpoints.length == 0) {
                    throw new Error("Endpoint `hotrod-route` missing");
                }
                previewURL = filteredEndpoints[0].previewURL;

                const readyStateInterval = setInterval(async () => {
                    const readyState = await workspacesApi.getWorkspaceReady(SIGNADOT_ORG, workspaceID);
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

    it('Route service preview', () => {
        const serviceURL = `${previewURL}/route?pickup=123&dropoff=456`

        axios.get(serviceURL, {
            headers: {
                'signadot-api-key': SIGNADOT_API_KEY
            }
        })
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
        console.log("Tests complete. Deleting workspace");
        return workspacesApi.deleteWorkspaceById(SIGNADOT_ORG, workspaceID);
    });
});
