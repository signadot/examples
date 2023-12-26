const redis = require('redis');
const { redisURL } = require('./../../../config/config.js');

const redisClient = redis.createClient({
    legacyMode: true,
    url: redisURL,
});

redisClient.on('connect', () => {
    console.log('Connected to ' + redisURL);
})

redisClient.on('error', (err) => {
    console.log('Redis error: ' + err.message);
})

redisClient.on('ready', () => {
    console.log('Redis is ready');
})

redisClient.on('end', () => {
    console.log('Redis connection ended');
})

redisClient.connect().then(() => {
}).catch((err) => {
    console.log(err.message);
})

module.exports = redisClient;