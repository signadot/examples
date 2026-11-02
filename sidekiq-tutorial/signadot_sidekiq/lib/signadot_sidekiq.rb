# frozen_string_literal: true

require "opentelemetry"
require "sidekiq"

require_relative "signadot_sidekiq/routing_rules"
require_relative "signadot_sidekiq/router"
require_relative "signadot_sidekiq/sweeper"

# Lets baseline and sandboxed Sidekiq workers share one Redis.
#
# A Sidekiq queue hands each job to exactly one worker, so each sandboxed
# worker reads its own queues ("default@<sandbox name>"). The baseline worker,
# the only reader of the shared queues, runs each job unless a sandbox claims
# the job's routing key; then it moves the job to that sandbox's queue.
#
# The routing key travels inside each job as W3C baggage, which the
# OpenTelemetry Sidekiq instrumentation adds when a job is pushed.
module SignadotSidekiq
  ROUTING_KEY = "sd-routing-key"

  # Call from Sidekiq.configure_server. Outside Signadot (no sandbox name and
  # no SIGNADOT_BASELINE_NAME) it changes nothing.
  def self.configure(config)
    sandbox = ENV.fetch("SIGNADOT_SANDBOX_NAME", "")
    if !sandbox.empty?
      # The Signadot Operator sets SIGNADOT_SANDBOX_NAME in sandboxed pods.
      config.on(:startup) { read_sandbox_queues(config, sandbox) }
    elsif ENV.key?("SIGNADOT_BASELINE_NAME")
      rules = RoutingRules.from_env(config.logger)
      config.server_middleware { |chain| chain.add Router, rules }
      config.on(:startup) do
        # Run no job before knowing which routing keys sandboxes claim.
        rules.load
        rules.start
        Sweeper.new(config, rules).start
      end
    end
  end

  def self.sandbox_queue(queue, sandbox)
    "#{queue}@#{sandbox}"
  end

  # The routing key in the job's W3C baggage, or nil.
  def self.routing_key(job)
    context = OpenTelemetry::Baggage::Propagation.text_map_propagator.extract(job)
    OpenTelemetry::Baggage.value(ROUTING_KEY, context: context)
  end

  # Swap every queue this process was started with for the sandbox's own,
  # keeping weights and order: "-q default -q notifications" reads
  # "default@<sandbox>" and "notifications@<sandbox>".
  def self.read_sandbox_queues(config, sandbox)
    config.capsules.each_value do |capsule|
      capsule.queues = capsule.weights.map { |queue, weight| [sandbox_queue(queue, sandbox), weight] }
      config.logger.info "sandbox #{sandbox}: reading queues #{capsule.weights.keys.join(", ")}"
    end
  end
  private_class_method :read_sandbox_queues
end
