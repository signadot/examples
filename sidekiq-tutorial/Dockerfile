FROM ruby:3.4-slim AS build

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY Gemfile Gemfile.lock ./
COPY signadot_sidekiq ./signadot_sidekiq
RUN bundle config set --local frozen true && bundle install

FROM ruby:3.4-slim

WORKDIR /usr/src/app
ENV RACK_ENV=production

COPY --from=build /usr/local/bundle /usr/local/bundle
COPY Gemfile Gemfile.lock ./
COPY signadot_sidekiq ./signadot_sidekiq
COPY app ./app
COPY config ./config

USER 1000
