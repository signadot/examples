const { kafkaTopic } = require('../../../config/config.js');
const { consumeMessages } = require('../../modules/kafka/kafka.js')
const { extractRoutingKey } = require('../../modules/otel/baggage.js');
const { registerEvent } = require('../../modules/events/events.js');


function runConsumer() {
    // consume messages from the queue
    consumeMessages(kafkaTopic, (msg, headers) => {
        let baggage = "";
        if (headers['baggage'] !== undefined) {
            baggage = headers['baggage'].toString();
        }
        registerEvent('Consumed message from kafka  (topic=' + kafkaTopic +')', msg, extractRoutingKey(baggage),
            () => { },
            (error) => console.error(error)
        )
    }).catch((error) => console.error(`Error in consumer: ${error.message}`));
}

module.exports = runConsumer;