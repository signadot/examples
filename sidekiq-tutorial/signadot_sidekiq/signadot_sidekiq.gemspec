# frozen_string_literal: true

Gem::Specification.new do |spec|
  spec.name = "signadot_sidekiq"
  spec.version = "0.1.0"
  spec.summary = "Route Sidekiq jobs between baseline and sandboxed workers in Signadot sandboxes"
  spec.authors = ["Signadot"]
  spec.homepage = "https://github.com/signadot/examples/tree/main/sidekiq-tutorial"
  spec.files = Dir["lib/**/*.rb"]
  spec.required_ruby_version = ">= 3.1"

  spec.add_dependency "opentelemetry-api", "~> 1.0"
  spec.add_dependency "sidekiq", ">= 7.1"
end
