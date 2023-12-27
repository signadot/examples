const { Kafka } = require('kafkajs');
const { kafkaAddr, baselineName } = require('./../../../config/config.js');

// Define the Kafka broker connection configuration
const kafka = new Kafka({
    clientId: baselineName,
    brokers: [kafkaAddr],
});

// Create a Kafka producer
const producer = kafka.producer();

// Create a Kafka consumer
const consumer = kafka.consumer({ groupId: 'test-group' });

// Function to send messages to a Kafka topic with headers
const publishMessage = async (topic, message, headers) => {
    await producer.connect();

    // Produce a message to the specified topic with headers
    await producer.send({
        topic,
        messages: [
            {
                value: JSON.stringify(message),
                headers: headers || {}, // Include headers if provided, or an empty object
            },
        ],
    });
};

// Function to process messages received from Kafka
const consumeMessages = async (topic, onNewMessage) => {
    await consumer.connect();

    // Subscribe to a Kafka topic
    await consumer.subscribe({ topic: topic, fromBeginning: true });

    // Start consuming messages
    await consumer.run({
        eachMessage: async ({ topic, partition, message }) => {
            // Parse value
            const value = JSON.parse(message.value.toString());
            console.log(`Received message from topic ${topic} on partition ${partition}:`, value);

            // Process the message
            onNewMessage(value, message.headers)

            // Commit the offset to mark the message as processed
            await consumer.commitOffsets([{ topic, partition, offset: message.offset }]);
        },
    });
};


module.exports = {
    publishMessage: publishMessage,
    consumeMessages, consumeMessages,
}