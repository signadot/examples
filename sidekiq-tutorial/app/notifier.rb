# frozen_string_literal: true

require "json"
require "sinatra/base"

require_relative "events"
require_relative "otel"

Otel.setup("notifier")
Events.service = "notifier"

class Notifier < Sinatra::Base
  get "/healthz" do
    "ok"
  end

  post "/api/notify" do
    message = JSON.parse(request.body.read)
    Events.record(message["id"], "Sent notification: \"#{message["body"]}\"")
    204
  end
end
