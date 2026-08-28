package com.signadot.temporaldemo.signadot;

import io.temporal.api.common.v1.Payload;
import io.temporal.common.converter.DataConverter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

public class OTelHeaderParsing {
    private static final Logger logger = LoggerFactory.getLogger(OTelHeaderParsing.class);
    private static final String ROUTING_KEY = "sd-routing-key";

    public static String extractRoutingKeyFromHeaders(Map<String, Payload> headers) {
        if (headers == null) {
            return "";
        }

        Payload tracerDataPayload = headers.get("_tracer-data");
        if (tracerDataPayload == null) {
            return "";
        }

        try {
            Map<?, ?> carrier = DataConverter.getDefaultInstance().fromPayload(
                tracerDataPayload,
                Map.class,
                Map.class
            );
            Object baggageValue = carrier.get("baggage");
            if (baggageValue == null) {
                return "";
            }

            for (String entry : baggageValue.toString().split(",")) {
                String pair = entry.trim().split(";", 2)[0];
                int equals = pair.indexOf('=');
                if (equals < 0) {
                    continue;
                }
                String key = pair.substring(0, equals).trim();
                if (ROUTING_KEY.equals(key)) {
                    return URLDecoder.decode(
                        pair.substring(equals + 1).trim(),
                        StandardCharsets.UTF_8
                    );
                }
            }
            return "";
        } catch (Exception e) {
            logger.debug("Failed to extract routing key from _tracer-data header: {}", e.getMessage());
            return "";
        }
    }

    public static String routingKeyFromContext(String routingKey) {
        return routingKey != null && !routingKey.isEmpty() ? routingKey : "";
    }
}
