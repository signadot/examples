# Multi-stage build
FROM golang:1.25.4-alpine AS builder

WORKDIR /workspace

# Copy go.mod and go.sum
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary for the image's target architecture (works on both
# amd64 and arm64 hosts, e.g. Apple Silicon minikube)
ARG TARGETOS
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -o worker .

# Runtime image (distroless for minimal footprint and security)
FROM gcr.io/distroless/base-debian12:nonroot

# Copy the binary from builder
COPY --from=builder /workspace/worker /worker

# Run as non-root (distroless enforces this by default)
ENTRYPOINT ["/worker"]
