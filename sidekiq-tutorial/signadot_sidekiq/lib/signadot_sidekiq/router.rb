# frozen_string_literal: true

module SignadotSidekiq
  # Server middleware for the baseline worker. It runs each job, unless a
  # sandbox claims the job's routing key: then it moves the job to that
  # sandbox's queue instead of running it.
  class Router
    include Sidekiq::ServerMiddleware

    def initialize(rules)
      @rules = rules
    end

    def call(_job_instance, job, queue)
      routing_key = SignadotSidekiq.routing_key(job)
      sandbox = routing_key && @rules.sandbox_for(routing_key)
      return yield unless sandbox

      target = SignadotSidekiq.sandbox_queue(queue, sandbox)
      # If the sandbox's attempt fails, Sidekiq retries it on retry_queue: the
      # shared queue, so the baseline decides again where the retry runs.
      Sidekiq::Client.push(job.merge("queue" => target, "retry_queue" => job["retry_queue"] || queue))
      logger.info "handed #{job["class"]} #{job["jid"]} (routing key #{routing_key}) to #{target}"
    end
  end
end
