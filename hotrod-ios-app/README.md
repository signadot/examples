# HotROD Microservices with Signadot Sandboxes

A demonstration of microservices architecture using HotROD (Hotrod On-Demand) ride-sharing application with Signadot sandbox isolation for testing and development.

## 🏗️ Architecture Overview

HotROD is a microservices-based ride-sharing application consisting of:

- **Frontend Service** (Port 8080) - Web UI and API gateway
- **Location Service** (Port 8081) - Manages pickup/dropoff locations
- **Driver Service** (Port 8082) - Handles driver assignment via Kafka
- **Route Service** (Port 8083) - Calculates optimal routes
- **MySQL Database** - Persistent data storage
- **Kafka** - Asynchronous messaging between services

## 🚀 Key Features

### Microservices Communication
- **HTTP REST APIs** for synchronous operations
- **Kafka messaging** for asynchronous driver dispatch
- **OpenTelemetry tracing** for observability
- **Prometheus metrics** for monitoring

### Signadot Sandbox Integration
- **Request-level traffic splitting** using routing headers
- **Database isolation** for location service
- **Enhanced driver ratings** in sandbox environment
- **iOS mobile app** for end-to-end testing

## 📱 iOS Mobile App

A modern SwiftUI application that demonstrates sandbox isolation:

### Features
- **Environment Selection** - Switch between production and sandbox
- **Location Browsing** - View available pickup/dropoff locations
- **Driver Selection** - See available drivers with ratings (sandbox only)
- **Ride Booking** - Complete ride booking flow
- **Sandbox Routing** - Automatic routing header injection

### Demo Scenarios
1. **Baseline Environment** - Standard locations, drivers without ratings
2. **Location Sandbox** - Enhanced locations including "Egyptian Treats"
3. **Driver Ratings Sandbox** - Drivers with ratings and trip counts

## 🛠️ Development Setup

### Prerequisites
- Docker Desktop with Kubernetes enabled
- Signadot CLI (`signadot auth login`)
- Xcode (for iOS app development)
- kubectl configured for local cluster

### Quick Start

1. **Deploy HotROD to Kubernetes**
   ```bash
   kubectl apply -f k8s/
   ```

2. **Create Signadot Sandboxes**
   ```bash
   signadot sandbox apply -f signadot-config/location-enhanced.yaml
   signadot sandbox apply -f signadot-config/driver-ratings.yaml
   ```

3. **Connect to Services**
   ```bash
   # For routing to work properly, use signadot local connect
   sudo signadot local connect --cluster local-hotrod-cluster
   
   # Alternative: Port forwarding (bypasses routing)
   kubectl port-forward svc/frontend 8080:8080 -n hotrod
   ```

4. **Run iOS App**
   ```bash
   cd hotrod/ios/HotRodApp
   open HotRodApp.xcodeproj
   # Build and run in Xcode
   ```

## 🔄 API Endpoints

### Frontend Service (`:8080`)
- `GET /` - Web UI
- `GET /splash` - Main page with locations
- `POST /dispatch` - Book a ride (triggers Kafka events)
- `GET /notifications` - Real-time ride updates
- `GET /healthz` - Health check

### Location Service (`:8081`)
- `GET /locations` - List all locations
- `GET /location` - Get specific location
- `POST /location` - Create location
- `DELETE /location` - Delete location

### Driver Service (`:8082`)
- `GET /healthz` - Health check only
- *No HTTP endpoints - Kafka-based processing*

## 🎯 Sandbox Configuration

### Location Enhanced Sandbox
```yaml
# signadot-config/location-enhanced.yaml
forks:
  - forkOf:
      kind: Deployment
      namespace: hotrod
      name: location
    customizations:
      images:
        - image: mostafamraafat/hotrod-location:dynamic-seed-v5
          container: hotrod
      env:
        - container: hotrod
          name: MYSQL_DATABASE
          value: "hotrod_sandbox"
```

### Driver Ratings Sandbox
```yaml
# signadot-config/driver-ratings.yaml
forks:
  - forkOf:
      kind: Deployment
      namespace: hotrod
      name: driver
    customizations:
      images:
        - image: mostafamraafat/hotrod-driver:ratings-v11
          container: hotrod
```

## 🔍 How Routing Works

### Request Flow
1. **iOS App** sends request with `signadot-routing-key` header
2. **Signadot DevMesh** intercepts request at service mesh level
3. **Traffic routing** directs request to appropriate service version
4. **Sandbox isolation** ensures separate data and behavior

### Key Headers
```
signadot-routing-key: <sandbox-routing-key>
```

### Database Isolation
- **Baseline**: Uses `hotrod` database
- **Sandbox**: Uses `hotrod_sandbox` database
- **Dynamic seeding**: Different locations per environment

## 🚨 Troubleshooting

### Common Issues

1. **Routing Not Working**
   - ❌ Don't use `kubectl port-forward` (bypasses DevMesh)
   - ✅ Use `sudo signadot local connect` for proper routing

2. **Sandbox Pod Not Starting**
   - Check image availability and architecture (ARM64 vs AMD64)
   - Verify Kubernetes node resources
   - Check sidecar injection status

3. **Database Connection Issues**
   - Ensure MySQL pods are running
   - Check environment variables in sandbox config
   - Verify database initialization

4. **iOS App Connection Issues**
   - Configure App Transport Security (ATS) for HTTP
   - Use correct base URL for signadot local connect
   - Check routing headers format

### Debugging Commands
```bash
# Check sandbox status
signadot sandbox list

# Check pod logs
kubectl logs -f deployment/location-enhanced-dep-location -n hotrod

# Test direct pod access
curl http://location-enhanced-dep-location-<pod-id>.hotrod:8081/locations

# Check local connect status
signadot local status
```

## 🏆 Demo Scenarios

### 1. Location Isolation Demo
- **Baseline**: 5 standard locations
- **Sandbox**: 6 locations including "Egyptian Treats"
- **Validation**: iOS app shows different location lists

### 2. Driver Ratings Demo
- **Baseline**: Drivers without ratings
- **Sandbox**: Drivers with ratings and trip counts
- **Validation**: iOS app shows enhanced driver information

### 3. End-to-End Flow
1. Select sandbox environment in iOS app
2. Browse enhanced locations
3. Select drivers with ratings
4. Book ride through `/dispatch` endpoint
5. Kafka events processed by sandbox services

## 📊 Architecture Benefits

- **Microservices Isolation** - Test individual services independently
- **Database Separation** - Sandbox data doesn't affect production
- **Request-Level Routing** - Per-request traffic splitting
- **Mobile Integration** - Real mobile app testing scenarios
- **Observability** - Full tracing and metrics collection

## 🔧 Technical Stack

- **Backend**: Go microservices
- **Database**: MySQL with environment-specific schemas
- **Messaging**: Kafka for async communication
- **Container**: Docker with Kubernetes orchestration
- **Service Mesh**: Signadot DevMesh for traffic routing
- **Mobile**: SwiftUI iOS application
- **Observability**: OpenTelemetry + Prometheus

## 📝 Next Steps

1. **Extend Sandbox Features** - Add more service variations
2. **Enhanced Mobile UI** - Improve user experience
3. **Automated Testing** - E2E test scenarios
4. **Production Deployment** - Scale beyond local development
5. **Monitoring Dashboard** - Real-time metrics visualization

---

*This project demonstrates modern microservices development with sandbox isolation, enabling safe testing and development of complex distributed systems.*
