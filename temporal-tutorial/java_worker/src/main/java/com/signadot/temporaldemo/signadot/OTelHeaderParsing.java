package com.signadot.temporaldemo.signadot;

import io.temporal.api.common.v1.Payload;
import io.temporal.common.converter.DataConverter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

public class OTelHeaderParsing {
    private static final Logger logger = LoggerFactory.getLogger(OTelHeaderParsing.class);

    /** Task header carrying the serialized OTel context (trace + baggage). */
    public static final String TRACER_DATA_HEADER = "_tracer-data";
    /** Baggage member carrying the Signadot routing key. */
    public static final String ROUTING_KEY = "sd-routing-key";

    /**
     * Decodes the _tracer-data header payload into the OTel carrier map
     * (e.g. {"traceparent": ..., "baggage": ...}). Returns null when the
     * header is absent or cannot be decoded.
     */
    public static Map<String, String> extractCarrier(Map<String, Payload> headers) {
        if (headers == null) {
            return null;
        }
        Payload tracerDataPayload = headers.get(TRACER_DATA_HEADER);
        if (tracerDataPayload == null) {
            return null;
        }
        try {
            Map<?, ?> raw = DataConverter.getDefaultInstance().fromPayload(
                tracerDataPayload,
                Map.class,
                Map.class
            );
            Map<String, String> carrier = new HashMap<>();
            for (Map.Entry<?, ?> entry : raw.entrySet()) {
                if (entry.getKey() != null && entry.getValue() != null) {
                    carrier.put(entry.getKey().toString(), entry.getValue().toString());
                }
            }
            return carrier;
        } catch (Exception e) {
            logger.debug("Failed to decode {} header: {}", TRACER_DATA_HEADER, e.getMessage());
            return null;
        }
    }

    public static String extractRoutingKeyFromHeaders(Map<String, Payload> headers) {
        return routingKeyFromCarrier(extractCarrier(headers));
    }

    /**
     * Extracts sd-routing-key from a decoded carrier map using a
     * deterministic string parse (a pure function with no I/O, safe to call
     * from workflow code).
     */
    public static String routingKeyFromCarrier(Map<String, String> carrier) {
        if (carrier == null) {
            return "";
        }
        String baggageValue = carrier.get("baggage");
        if (baggageValue == null) {
            return "";
        }

        for (String entry : baggageValue.split(",")) {
            String pair = entry.trim().split(";", 2)[0];
            int equals = pair.indexOf('=');
            if (equals < 0) {
                continue;
            }
            String key = pair.substring(0, equals).trim();
            if (ROUTING_KEY.equals(key)) {
                String value = pair.substring(equals + 1).trim();
                // Percent-decode without treating '+' as a space: W3C baggage
                // values may contain literal '+'.
                return URLDecoder.decode(value.replace("+", "%2B"), StandardCharsets.UTF_8);
            }
        }
        return "";
    }
}
