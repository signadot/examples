# frozen_string_literal: true

module SignadotSidekiq
  # Runs in the baseline worker. When a sandbox is deleted, jobs can be left in
  # its queues: ones it never started, and ones Sidekiq pushed back when it
  # stopped mid-job. Once the sandbox has been gone for a grace period, this
  # moves them to the shared queue, where the baseline runs them.
  class Sweeper
    # The grace period outlasts Sidekiq's 25-second shutdown timeout, and lets
    # every baseline replica see a new sandbox before its queue could be swept.
    def initialize(config, rules, interval: 10, grace: 30)
      @config = config
      @rules = rules
      @interval = interval
      @grace = grace
      @queues = config.capsules.values.flat_map { |capsule| capsule.weights.keys }.uniq
      @gone_since = {} # sandbox queue => when its sandbox was first seen gone
    end

    def start
      Thread.new do
        loop do
          sleep @interval
          sweep
        rescue StandardError => e
          @config.logger.warn "could not sweep sandbox queues: #{e.message}"
        end
      end
    end

    private

    def sweep
      active = @rules.sandbox_names
      @config.redis do |conn|
        # Sidekiq records every queue it pushes to in the "queues" set.
        conn.call("SMEMBERS", "queues").each do |name|
          queue, _, sandbox = name.rpartition("@")
          next unless @queues.include?(queue)

          if active.include?(sandbox)
            @gone_since.delete(name)
          elsif now - (@gone_since[name] ||= now) >= @grace
            move_back(conn, name, queue, sandbox)
            @gone_since.delete(name)
          end
        end
      end
    end

    def move_back(conn, name, queue, sandbox)
      moved = 0
      moved += 1 while conn.call("LMOVE", "queue:#{name}", "queue:#{queue}", "RIGHT", "LEFT")
      conn.call("SREM", "queues", name)
      @config.logger.info "sandbox #{sandbox} is gone: moved #{moved} job(s) from #{name} to #{queue}"
    end

    def now
      Process.clock_gettime(Process::CLOCK_MONOTONIC)
    end
  end
end
