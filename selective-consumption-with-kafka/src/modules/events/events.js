const redisClient = require('./init_redis')
const { baselineNamespace, baselineName, sandboxName } = require('./../../../config/config.js');


function constructEvent(logEntry, message) {
    return {
        timestamp: new Date(),
        logEntry: logEntry,
        context: {
            baselineWorkload: {
                namespace: baselineNamespace,
                name: baselineName,
            },
            routingKey: "", // TODO
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

function getEvents(eventsCursor, cursor, onSuccess, onError, match = 'event-*', count = 10) {
    var events = []
    var lastEventID = 0

    // Scan all events from redis
    redisClient.SCAN(cursor, 'MATCH', match, 'COUNT', count, (err, reply) => {
        if (err) {
            console.error(err);
            onError("couldn't scan events")
            return;
        }
        const [newCursor, keys] = reply;

        // Use MGET to get values for all keys in the current batch
        if (keys.length > 0) {
            redisClient.MGET(keys, (err, values) => {
                if (err) {
                    console.error(err);
                    onError("couldn't read events");
                    return
                }

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

                // Continue scanning if the new cursor is not '0'
                if (newCursor !== '0') {
                    getEvents(eventsCursor, newCursor, onSuccess, onError);
                    return;
                }

                // We are done
                events.sort((a, b) => a.timestamp - b.timestamp);
                onSuccess(events, lastEventID);
            });
            return;
        }

        // Continue scanning if the new cursor is not '0'
        if (newCursor !== '0') {
            getEvents(eventsCursor, newCursor, onSuccess, onError);
            return;
        }

        // We are done
        events.sort((a, b) => a.timestamp - b.timestamp);
        onSuccess(events, lastEventID);
    });
}

module.exports = {
    constructEvent: constructEvent,
    storeEvent: storeEvent,
    getEvents: getEvents,
}