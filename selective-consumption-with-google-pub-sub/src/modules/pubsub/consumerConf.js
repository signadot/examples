let conf = {
    "filter": "",
    "enableExactlyOnceDelivery": true,
    "messageRetentionDuration": {
        "seconds": 3600
    },
    "expirationPolicy": {
        "ttl": {
            "seconds": 86400
        }
    },
    "ackDeadlineSeconds": 600,
    "retryPolicy": {
        "minimumBackoff": {
            "seconds": 60
        },
        "maximumBackoff": {
            "seconds": 120
        }
    }          
}