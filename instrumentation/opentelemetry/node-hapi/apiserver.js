'use strict';

const Hapi = require('@hapi/hapi');
const http = require('http');

const init = async () => {
    const server = Hapi.server({
        port: 3000,
        host: 'localhost'
    });

    server.route({
        method: 'GET',
        path: '/',
        handler: (request, h) => {
            let resp = 'Baggage header seen by API server: ' + request.headers.baggage + '\n';

            return new Promise((resolve, reject) => {
                http.get('http://localhost:3001/', (backendRes) => {
                    let data = '';
                    backendRes.on('data', (chunk) => { data += chunk; });
                    backendRes.on('end', () => {
                        resp += data;
                        resolve(resp);
                    });
                });
            });
        }
    });

    await server.start();
    console.log('API server running on %s', server.info.uri);
};

process.on('unhandledRejection', (err) => {
    console.log(err);
    process.exit(1);
});

init();
