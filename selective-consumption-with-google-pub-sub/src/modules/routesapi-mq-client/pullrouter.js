const { routeServerAddr, baselineKind, baselineNamespace, baselineName, sandboxName } = require('./../../../config/config.js');

const http = require('http');
const url = require('url');
const NodeCache = require('node-cache');


// Construct the routeserver URL
var queryParams = {
    'baselineKind': baselineKind,
    'baselineNamespace': baselineNamespace,
    'baselineName': baselineName
}
if (sandboxName !== "") {
    queryParams.destinationSandboxName = sandboxName
}
var routeServerURL = url.format({
    protocol: 'http',
    host: routeServerAddr,
    pathname: '/api/v1/workloads/routing-rules',
    query: queryParams,
});


// Create the cache
const cache = new NodeCache();


function run() {
    // initial load of routes
    getRoutes();
    // reload routes every 5 seconds
    setInterval(getRoutes, 5 * 1000);
}

// Load routes from routeserver and update our cache (storing the obtained
// routing keys)
function getRoutes() {
    console.log('Sending request to routeserver, url=' + routeServerURL)

    const req = http.get(routeServerURL, (res) => {
        let data = '';

        res.on('data', (chunk) => {
            data += chunk;
        });

        res.on('end', () => {
            try {
                // parse routes
                const jsonData = JSON.parse(data);
                let routingKeys = new Set();
                if (jsonData['routingRules'] !== undefined) {
                    for (var i in jsonData.routingRules) {
                        routingKeys.add(jsonData.routingRules[i].routingKey)
                    }
                }

                // update cache
                console.log("Routing keys received: [" + Array.from(routingKeys).join(', ') + ']')
                cache.set('routingKeys', routingKeys);
            } catch (error) {
                console.error('Error parsing routes:', error.message);
            }
        });
    });

    req.on('error', (error) => {
        console.error('Error getting routes:', error.message);
    });

    req.end();
}

// Function to get cached data
function shouldProcess(routingKey) {
    const routingKeys = cache.get('routingKeys');
    if (sandboxName !== "") {
        // we are a sandboxed workload, only accept the received routing keys
        return routingKeys.has(routingKey)
    }
    // we are a baseline workload, ignore received routing keys (they belong
    // to sandboxed workloads)
    return !routingKeys?.has(routingKey)
}

module.exports = {
    run: run,
    shouldProcess: shouldProcess
};
