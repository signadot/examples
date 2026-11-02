# frozen_string_literal: true

require "json"
require "opentelemetry"
require "redis-client"
require "time"

# Event log that the walkthrough reads to show which version of each service
# handled each step of a message. Demo only: it reads the routing key and the
# sandbox name just to display them.
module Events
  KEY = "demo:events"
  REDIS = RedisClient.config(url: ENV.fetch("REDIS_URL", "redis://redis:6379")).new_pool(size: 5)

  class << self
    attr_accessor :service

    def record(message_id, text)
      event = JSON.generate(
        time: Time.now.utc.iso8601(3),
        service: service,
        sandbox: ENV.fetch("SIGNADOT_SANDBOX_NAME", ""),
        routingKey: OpenTelemetry::Baggage.value("sd-routing-key") || "",
        messageId: message_id,
        text: text
      )
      puts event
      REDIS.pipelined do |pipeline|
        pipeline.call("LPUSH", KEY, event)
        pipeline.call("LTRIM", KEY, 0, 999)
      end
    end

    def all
      REDIS.call("LRANGE", KEY, 0, -1).reverse.map { |event| JSON.parse(event) }
    end
  end
end
