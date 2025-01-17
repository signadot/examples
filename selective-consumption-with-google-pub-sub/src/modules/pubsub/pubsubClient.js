// Imports the Google Cloud client library
const { PubSub } = require('@google-cloud/pubsub');
const path = require('path')

const pubSubClient = new PubSub({
    projectId: process.env.PROJECT_ID
});

exports.pubSubClient = pubSubClient;