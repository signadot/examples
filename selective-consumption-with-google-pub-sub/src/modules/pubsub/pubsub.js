const { pubSubClient } = require('./pubsubClient.js');
const { sandboxName, pubsubTopic } = require('./../../../config/config.js');
const groupId = 'pubsub-grp';

// This sets the consumer group with suffix '-' + <sandbox-name> if running in
// sandboxed workload, otherwise, it just returns the argument.
function signadotConsumerGroup(sGroupId) {
    
    if (sandboxName !== "") {
        sGroupId += '-' + sandboxName
    }
    return sGroupId
}

async function createSubscription(subscriptionName){
    let [subscription] = await pubSubClient.createSubscription(pubsubTopic, subscriptionName, {
        enableExactlyOnceDelivery: true,
        ackDeadlineSeconds: 300,
        retryPolicy: {
            minimumBackoff: {
                seconds: 2
            },
            maximumBackoff: {
                seconds: 120
            }
        }          
    })
    .catch(ex => {
        console.log(ex);                
    })
    return subscription;
}

async function initializePubSubResources(callback) { // wrapper
    let subscriptionName = signadotConsumerGroup(groupId);

    // Step 1: Create the topic if it doesn't exist
    try {
        await pubSubClient.topic(pubsubTopic).get({ autoCreate: true });
        console.log(`Topic '${pubsubTopic}' is ready.`);
    } catch (error) {
        console.error(`Error creating topic '${pubsubTopic}':`, error);
    }

    // Step 2: Create the subscription if it doesn't exist
    try {
        const [sub] = await pubSubClient.topic(pubsubTopic).getSubscriptions();
        const subscriptionExists = sub.some(s => s.name.split('/').pop() === subscriptionName);
        let subscription;
        if (!subscriptionExists) {
            subscription = await createSubscription(subscriptionName)
        }
        else{
            // Fetch the existing subscription
            subscription = pubSubClient.subscription(subscriptionName);
            console.log(`Listening to existing subscription: ${subscription.name}`);
        }

        if (subscription) {
            // Set up message listener
            subscription.on('message', callback);
    
            // Set up error listener
            subscription.on('error', (error) => {
                console.error(`Subscription error: ${error.message}`);
            });
    
            console.log(`Subscription '${subscriptionName}' is now active.`);
        }
    } catch (error) {
        console.error(`Error creating subscription '${subscriptionName}':`, error);
    }
}

// Function to publish messages to a Pub/Sub topic
const publishMessages = async (topicName, message, headers) => {
    try {
        // Convert the message to a buffer
        const dataBuffer = Buffer.from(JSON.stringify({
            value: JSON.stringify(message),
            headers: headers || {}, // Include headers if provided, or an empty object
        }));

        // Publish a message to the specified topic with attributes
        await pubSubClient.topic(topicName).publishMessage({
            data: dataBuffer
        });
        
    } catch (error) {
        console.error(`Error publishing message to topic ${topicName}:`, error);
    }
};

module.exports = {
    initializePubSubResources: initializePubSubResources,
    publishMessages: publishMessages
}
