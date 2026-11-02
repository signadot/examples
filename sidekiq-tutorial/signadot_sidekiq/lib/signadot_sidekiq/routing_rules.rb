# frozen_string_literal: true

require "json"
require "net/http"

module SignadotSidekiq
  # Which sandboxes of this worker's baseline claim which routing keys,
  # according to the Signadot Routes API. A sandbox claims its own routing key
  # and the keys of the route groups it belongs to.
  class RoutingRules
    # The baseline is the Deployment that sandboxes fork, set in its env.
    def self.from_env(logger)
      new(
        routeserver: ENV.fetch("SIGNADOT_ROUTESERVER", "routeserver.signadot.svc:7778"),
        baseline_kind: ENV.fetch("SIGNADOT_BASELINE_KIND", "Deployment"),
        baseline_namespace: ENV.fetch("SIGNADOT_BASELINE_NAMESPACE"),
        baseline_name: ENV.fetch("SIGNADOT_BASELINE_NAME"),
        logger: logger
      )
    end

    def initialize(routeserver:, baseline_kind:, baseline_namespace:, baseline_name:, logger:, interval: 5)
      @uri = URI("http://#{routeserver}/api/v1/workloads/routing-rules")
      @uri.query = URI.encode_www_form(baselineKind: baseline_kind,
                                       baselineNamespace: baseline_namespace,
                                       baselineName: baseline_name)
      @logger = logger
      @interval = interval
      @sandboxes = {} # routing key => name of the sandbox it routes to
    end

    # The name of the sandbox that claims routing_key, or nil.
    def sandbox_for(routing_key)
      @sandboxes[routing_key]
    end

    def sandbox_names
      @sandboxes.values.uniq
    end

    # Blocks until the rules have been read once.
    def load
      refresh(log: true)
    rescue StandardError => e
      @logger.warn "waiting for the Signadot Routes API: #{e.message}"
      sleep @interval
      retry
    end

    # Refreshes the rules in the background.
    def start
      Thread.new do
        loop do
          sleep @interval
          refresh
        rescue StandardError => e # keep the last known rules
          @logger.warn "could not refresh Signadot routing rules: #{e.message}"
        end
      end
    end

    private

    def refresh(log: false)
      response = Net::HTTP.start(@uri.host, @uri.port, open_timeout: 5, read_timeout: 5) do |http|
        http.get(@uri.request_uri)
      end
      response.value # raises unless 2xx
      rules = JSON.parse(response.body)["routingRules"] || []
      sandboxes = rules.to_h { |rule| [rule["routingKey"], rule.dig("destinationSandbox", "name")] }
      @logger.info "routing keys claimed by sandboxes: #{sandboxes}" if log || sandboxes != @sandboxes
      @sandboxes = sandboxes
    end
  end
end
