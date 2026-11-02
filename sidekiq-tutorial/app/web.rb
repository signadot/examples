# frozen_string_literal: true

require "json"
require "sinatra/base"

require_relative "events"
require_relative "jobs"
require_relative "otel"

Otel.setup("web")
Events.service = "web"

class Web < Sinatra::Base
  get "/healthz" do
    "ok"
  end

  # Enqueues a ProcessMessageJob. "delay" schedules it with perform_in, and
  # "failOnce" makes its first attempt fail.
  post "/api/messages" do
    data = JSON.parse(request.body.read)
    id = data.fetch("id")
    args = [id, data.fetch("body"), data.fetch("failOnce", false)]
    if (delay = data["delay"])
      Events.record(id, "Scheduling ProcessMessageJob in #{delay}s")
      jid = ProcessMessageJob.perform_in(delay, *args)
    else
      Events.record(id, "Enqueuing ProcessMessageJob")
      jid = ProcessMessageJob.perform_async(*args)
    end
    content_type :json
    JSON.generate(jid: jid)
  end

  get "/api/events" do
    content_type :json
    JSON.generate(Events.all)
  end
end
