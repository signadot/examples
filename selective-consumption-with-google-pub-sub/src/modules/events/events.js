const redisClient = require('./init_redis')
const { baselineNamespace, baselineName, sandboxName } = require('./../../../config/config.js');


function registerEvent(logEntry, message, routingKey, onSuccess, onError) {
    storeEvent(constructEvent(logEntry, message, routingKey), onSuccess, onError)
}

function constructEvent(logEntry, message, routingKey) {
    return {
        timestamp: new Date(),
        logEntry: logEntry,
        context: {
            baselineWorkload: {
                namespace: baselineNamespace,
                name: baselineName,
            },
            routingKey: routingKey,
            sandboxName: sandboxName,
            message: message,
        }
    }
}

function storeEvent(event, onSuccess, onError) {
    generateEventID((eventID) => {
        redisClient.SETEX("event-" + eventID, 30, JSON.stringify({
            id: eventID,
            body: event,
        }), (err) => {
            if (err) {
                console.error(err);
                onError("couldn't store event in redis")
                return;
            }
            console.log('Successfully stored event id=' + eventID + ', body=' + JSON.stringify(event) + ' in redis');
            onSuccess();
        });
    }, onError)
}

function generateEventID(onSuccess, onError) {
    // Use INCR to get an incrementing number
    redisClient.INCR("event_counter", (err, eventID) => {
        if (err) {
            console.error(err);
            onError("couldn't generate event ID")
            return;
        }
        onSuccess(eventID);
    });
}

function getEvents(eventsCursor, cursor, onSuccess, onError) {
    let events = []
    let lastEventID = 0

    let collectEvents = (cursor) => {

        let checkResults = (newCursor) => {
            // Continue scanning if the new cursor is not '0'
            if (newCursor !== '0') {
                collectEvents(newCursor);
                return;
            }

            // We are done, sort results and call the on success callback
            events.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            onSuccess(events, lastEventID);
        }

        // Scan all events from redis (in batches of 10 records)
        redisClient.SCAN(cursor, 'MATCH', 'event-*', 'COUNT', 10, (err, reply) => {
            if (err) {
                console.error(err);
                onError("couldn't scan events")
                return;
            }
            const [newCursor, keys] = reply;

            // Read the scanned events, use MGET to get values for all keys in
            // the current batch
            if (keys.length > 0) {
                redisClient.MGET(keys, (err, values) => {
                    if (err) {
                        console.error(err);
                        onError("couldn't read events");
                        return
                    }

                    // collect events
                    keys.forEach((key, index) => {
                        var event = JSON.parse(values[index]);
                        if (event.id <= eventsCursor) {
                            return;
                        }
                        if (event.id > lastEventID) {
                            lastEventID = event.id
                        }
                        events.push(event.body)
                    });

                    // check results
                    checkResults(newCursor);
                });
                return;
            }

            // check results
            checkResults(newCursor);
        });
    }

    collectEvents(cursor);
}

function setKeys(key, value){
    redisClient.set(key, value);
}

async function getKeys(key) {
    let value = await redisClient.get(key)
    return value
}

module.exports = {
    registerEvent: registerEvent,
    getEvents: getEvents,
    setKeys: setKeys,
    getKeys: getKeys
}