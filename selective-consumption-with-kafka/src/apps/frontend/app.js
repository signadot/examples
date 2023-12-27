const express = require('express');
const path = require('path');
const http = require('http');

const { extractRoutingKey } = require('../../modules/otel/baggage.js');
const { registerEvent, getEvents } = require('../../modules/events/events.js');
const { frontendPort, producerPort, producerHost } = require('../../../config/config.js');


function runFrontend() {
    const app = express();

    // Middleware to parse JSON bodies
    app.use(express.json());

    // Middleware to parse URL-encoded form data
    app.use(express.urlencoded({ extended: true }));

    // Serve static files from the public folder
    app.use(express.static(path.join(__dirname, 'public')));

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
    app.post('/api/publish', (req, res) => {
        let msg = {
            id: req.body.messageID,
            body: req.body.messageBody
        }
        let routingKey = extractRoutingKey(req.get('baggage'));

        // Register an event
        registerEvent('Sending publish request to producer API', msg, routingKey,
            () => { },
            (error) => {
                console.error(error);
            }
        )

        // This endpoint is a passthru to the producer API
        const options = {
            hostname: producerHost,
            port: producerPort,
            path: "/api/publish",
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Create the request
        const producerReq = http.request(options, (producerRes) => {
            let data = '';
            producerRes.on('data', (chunk) => {
                data += chunk;
            });
            producerRes.on('end', () => {
                res.json({});
            });
        });

        // Handle errors
        producerReq.on('error', (error) => {
            // return an error
            errorHandler(res, error.message);
        });

        // Write the data to the request body
        producerReq.write(JSON.stringify(req.body));
        producerReq.end();
    });

    app.get('/api/events', (req, res) => {
        // Read events starting from cursor
        getEvents(req.query.cursor, 0, (events, eventsCursor) => {
            res.json({
                events: events,
                cursor: eventsCursor,
            });
        }, (error) => {
            // return an error
            errorHandler(res, error);
        })
    });

    // Route to the main HTML page
    app.get('/', (req, res) => {
        res.sendFile(path.join(__dirname, 'public', 'index.html'));
    });

    // Start the server
    app.listen(frontendPort, () => {
        console.log(`Frontend API is running at http://localhost:${frontendPort}`);
    });
}

module.exports = runFrontend;