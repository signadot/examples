const { baggageUtils } = require('@opentelemetry/core');

function extractRoutingKey(baggageHeader) {
    // Parse baggage
    let records = baggageUtils.parseKeyPairsIntoRecord(baggageHeader)

    // Get the value of a specific key from the baggage
    return records['sd-routing-key'];
}

module.exports = {
    extractRoutingKey: extractRoutingKey,
};