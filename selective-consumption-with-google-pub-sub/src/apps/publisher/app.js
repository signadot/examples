const express = require('express');
const { producerPort, pubsubTopic } = require('../../../config/config.js');
const { publishMessages } = require('../../modules/pubsub/pubsub.js')
const { extractRoutingKey } = require('../../modules/otel/baggage.js');
const { registerEvent } = require('../../modules/events/events.js');

function runProducer() {
    const app = express();

    // Middleware to parse JSON bodies
    app.use(express.json());

    // Middleware to parse URL-encoded form data
    app.use(express.urlencoded({ extended: true }));


    let errorHandler = (res, error) => {
        console.error(error);
        res.status(500);
        res.json({
            error: {
                message: error || 'Internal Server Error',
            },
        });
    }

    // REST API endpoints
    app.post('/api/publish', async (req, res) => {
        msg = {
            id: req.body.messageID,
            body: req.body.messageBody
        }

        let routingKey = extractRoutingKey(req.get('baggage')); 

        registerEvent('Publishing message to pubsub (topic=' + pubsubTopic +')', msg, routingKey,
            () => { },
            (error) => errorHandler(res, error)
        )

        publishMessages(pubsubTopic, msg, { baggage: req.get('baggage') })
            .then(() => {
                console.log('Message successfully published to pubsub')
                res.json({})
            })
            .catch((error) => errorHandler(res, error));
    });

    // Start the server
    app.listen(producerPort, () => {
        console.log(`Producer API is running at http://localhost:${producerPort}`);
    });
}

module.exports = runProducer;