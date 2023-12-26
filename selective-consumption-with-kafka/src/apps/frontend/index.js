const express = require('express');
const path = require('path');

const { constructEvent, storeEvent, getEvents } = require('./../../modules/events/events.js');
const { frontendPort, producerAddr } = require('./../../../config/config.js');


function runFrontend() {
    const app = express();

    // Middleware to parse JSON bodies
    app.use(express.json());

    // Middleware to parse URL-encoded form data
    app.use(express.urlencoded({ extended: true }));

    // Serve static files from the public folder
    app.use(express.static(path.join(__dirname, 'public')));

    // REST API endpoints
    app.post('/api/publish', (req, res) => {
        // Construct an event
        var event = constructEvent('Sent publish request to producer API', {
            id: req.body.messageID,
            body: req.body.messageBody
        });

        // Store the event
        storeEvent(event, () => {
            res.json({});
        }, (error) => {
            console.error(error);
            res.status(500);
            res.json({
                error: {
                    message: error || 'Internal Server Error',
                },
            });
        })

    });

    app.get('/api/events', (req, res) => {
        // Read events starting from cursor
        getEvents(req.query.cursor, 0, (events, eventsCursor) => {
            res.json({
                events: events,
                cursor: eventsCursor,
            });
        }, (error) => {
            console.error(error);
            res.status(500);
            res.json({
                error: {
                    message: error || 'Internal Server Error',
                },
            });
        })
    });

    // Route to the main HTML page
    app.get('/', (req, res) => {
        res.sendFile(path.join(__dirname, 'public', 'index.html'));
    });

    // Start the server
    app.listen(frontendPort, () => {
        console.log(`Server is running at http://localhost:${frontendPort}`);
    });
}

module.exports = runFrontend;