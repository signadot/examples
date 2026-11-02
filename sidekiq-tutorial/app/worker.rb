# frozen_string_literal: true

# Loaded by `sidekiq -r ./app/worker.rb`. In a Rails app, this setup goes in
# config/initializers/sidekiq.rb.
require "signadot_sidekiq"

require_relative "events"
require_relative "jobs"
require_relative "otel"

Otel.setup("worker")
Events.service = "worker"

Sidekiq.configure_server do |config|
  # From the platform team: lets baseline and sandboxed workers share queues.
  SignadotSidekiq.configure(config)
end
