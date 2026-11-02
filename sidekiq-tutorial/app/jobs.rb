# frozen_string_literal: true

require "json"
require "net/http"
require "sidekiq"

require_relative "events"

NOTIFIER_URL = ENV.fetch("NOTIFIER_URL", "http://notifier:4001")
# v1 keeps the message body as is; v2 uppercases it.
PROCESSOR_VERSION = ENV.fetch("PROCESSOR_VERSION", "v1")

class ProcessMessageJob
  include Sidekiq::Job
  # Retry after 5 seconds instead of Sidekiq's backoff, to keep the demo quick.
  sidekiq_retry_in { 5 }

  def perform(id, body, fail_once = false)
    if fail_once && first_attempt?(id)
      Events.record(id, "ProcessMessageJob failed on purpose; Sidekiq will retry it")
      raise "simulated failure for #{id}"
    end

    body = body.upcase if PROCESSOR_VERSION == "v2"
    Events.record(id, "ProcessMessageJob ran with processor #{PROCESSOR_VERSION}: \"#{body}\"")
    # Pushed while this job's context is current, so it carries the same
    # routing key.
    NotifyJob.perform_async(id, body)
  end

  private

  def first_attempt?(id)
    Sidekiq.redis { |conn| conn.call("SET", "demo:failed:#{id}", "1", "NX", "EX", 3600) } == "OK"
  end
end

class NotifyJob
  include Sidekiq::Job
  sidekiq_options queue: "notifications"

  def perform(id, body)
    Events.record(id, "NotifyJob ran")
    # The Net::HTTP instrumentation adds the job's baggage, and so its routing
    # key, to this call.
    Net::HTTP.post(URI("#{NOTIFIER_URL}/api/notify"), JSON.generate(id: id, body: body),
                   "Content-Type" => "application/json").value
  end
end
