# frozen_string_literal: true

require "opentelemetry/sdk"
require "opentelemetry/instrumentation/net/http"
require "opentelemetry/instrumentation/sidekiq"
require "opentelemetry/instrumentation/sinatra"

module Otel
  # Standard OpenTelemetry setup. No exporter is needed: the instrumentation
  # alone carries the W3C trace context and baggage, which holds the Signadot
  # routing key, from HTTP requests into Sidekiq jobs and back out.
  def self.setup(service_name)
    ENV["OTEL_TRACES_EXPORTER"] ||= "none"
    OpenTelemetry::SDK.configure do |c|
      c.service_name = service_name
      c.use "OpenTelemetry::Instrumentation::Sinatra"
      c.use "OpenTelemetry::Instrumentation::Net::HTTP"
      c.use "OpenTelemetry::Instrumentation::Sidekiq"
    end
  end
end
