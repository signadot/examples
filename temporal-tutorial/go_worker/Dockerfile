# Multi-stage build
FROM golang:1.25.4-alpine AS builder

WORKDIR /workspace

# Copy go.mod and go.sum
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o worker .

# Runtime image (distroless for minimal footprint and security)
FROM gcr.io/distroless/base-debian12:nonroot

# Copy the binary from builder
COPY --from=builder /workspace/worker /worker

# Run as non-root (distroless enforces this by default)
ENTRYPOINT ["/worker"]
