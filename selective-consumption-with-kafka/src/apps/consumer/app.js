const { kafkaTopic } = require('../../../config/config.js');
const { consumeMessages } = require('../../modules/kafka/kafka.js')
const { extractRoutingKey } = require('../../modules/otel/baggage.js');
const { registerEvent } = require('../../modules/events/events.js');

const { run, shouldProcess } = require('../../modules/routesapi-mq-client/pullrouter.js')


function runConsumer() {
    // start the router
    run();

    // consume messages from the queue
    consumeMessages(kafkaTopic, (msg, headers) => {
        let baggage = "";
        if (headers['baggage'] !== undefined) {
            baggage = headers['baggage'].toString();
        }
        let routingKey = extractRoutingKey(baggage);
        if (!shouldProcess(routingKey)) {
            // skip this message
            return
        }

        registerEvent('Consumed message from kafka  (topic=' + kafkaTopic + ')', msg, extractRoutingKey(baggage),
            () => { },
            (error) => console.error(error)
        )
    }).catch((error) => console.error(`Error in consumer: ${error.message}`));
}

module.exports = runConsumer;