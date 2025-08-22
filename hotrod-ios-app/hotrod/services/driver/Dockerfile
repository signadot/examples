# syntax=docker/dockerfile:1.4

# 🚧 Builder stage (with proper platform isolation)
FROM --platform=$BUILDPLATFORM golang:1.22 AS builder

# Declare build arguments for multi-platform support
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH
ARG BUILDPLATFORM

WORKDIR /app
COPY . .

# 🏗 Build the hotrod binary with driver command support
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    CGO_ENABLED=0 \
    GOOS=${TARGETOS:-linux} \
    GOARCH=${TARGETARCH} \
    go build -ldflags='-w -s -extldflags "-static"' -a -installsuffix cgo -o hotrod ./cmd/hotrod && \
    chmod +x hotrod

# 🏁 Final stage: minimal image
FROM gcr.io/distroless/base
WORKDIR /
COPY --from=builder /app/hotrod /
CMD ["/hotrod", "driver"]