const { pubsubTopic } = require('../../../config/config.js');
const { extractRoutingKey } = require('../../modules/otel/baggage.js');
const { registerEvent } = require('../../modules/events/events.js');
const { initializePubSubResources } = require('../../modules/pubsub/pubsub.js')
const { run, shouldProcess } = require('../../modules/routesapi-mq-client/pullrouter.js')

const consumerListener = (msg, headers) => {
    let baggage = "";
    if (headers['baggage'] !== undefined) {
        baggage = headers['baggage'].toString();
    }
    let routingKey = extractRoutingKey(baggage);

    if (!shouldProcess(routingKey)) {
        // skip this message
        return
    }        
    
    registerEvent('Consumed message from pubsub  (topic=' + pubsubTopic + ')', msg, extractRoutingKey(baggage),
        () => { },
        (error) => console.error(error)
    )
}

function callbackListener(message) {
    try {
        let data = Buffer.from(message.data);                                                            
        data = JSON.parse(data);
        console.log(`Received message from pubsub subscription:`, JSON.stringify(data));      

        // Process the message
        consumerListener(JSON.parse(data.value), data.headers);

        // Acknowledge the message
        message.ack();

        
    } catch (error) {
        message.nack();
        console.error(`Error processing message from subscription:`, error);
    }
}

async function runConsumer() {       
    // start the router
    run();
    await initializePubSubResources(callbackListener);  
}

module.exports = runConsumer;