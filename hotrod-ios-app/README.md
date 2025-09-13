# HotROD iOS App - Signadot Sandbox Testing

A modern, beautiful iOS app built with SwiftUI to test HotROD microservices using Signadot sandboxes. This app demonstrates how mobile developers can test backend changes in isolation before they reach production.

## 🚀 Features

### 🎯 Core Functionality
- **Ride Booking Interface**: Complete ride booking flow with location selection, driver selection, and trip management
- **Signadot Sandbox Integration**: Switch between production, sandbox, and route group environments
- **Fast ETA Feature Testing**: Test route service with ETA calculations in seconds instead of minutes
- **SD License Plate Testing**: Test driver service with "SD-" prefixed license plates for branding
- **Combined Feature Testing**: Test both fast ETA and SD license plates together using route groups

### 🎨 Modern UI/UX
- **Beautiful SwiftUI Interface**: Modern, clean design with gradient buttons and card layouts
- **Developer Debug Panel**: Toggle-able debug interface for environment switching
- **Real-time Status Updates**: Live trip status with animated state changes
- **Comprehensive Trip Details**: Detailed trip information with driver ratings and route visualization
- **Rating System**: Post-trip rating interface with star ratings and comments

### 🔧 Technical Features
- **Environment Switching**: Seamless switching between production and sandbox environments
- **Routing Header Support**: Automatic injection of Signadot routing headers
- **Mock & Real API Support**: Both mock data for testing and real HotROD API integration
- **State Management**: Centralized app state with ObservableObject pattern
- **Error Handling**: Comprehensive error handling with user-friendly messages

## 📱 App Structure

```
HotRodApp/
├── HotRodAppApp.swift          # Main app entry point
├── ContentView.swift           # Root navigation view
├── Models.swift                # Data models and app state
├── Services/
│   └── APIService.swift        # API integration (HotROD + Mock)
└── Views/
    ├── HomeView.swift          # Main ride booking interface
    ├── EnvironmentSelectorView.swift # Sandbox environment selector
    ├── TripInfoView.swift      # Trip details and management
    └── RatingView.swift        # Post-trip rating interface
```

## 🏗️ Architecture

### Models
- **EnvironmentOption**: Represents different testing environments (production, sandbox, route group)
- **Driver**: Driver information with optional ratings and trip history
- **Trip**: Complete trip information with status tracking
- **AppState**: Centralized app state management

### Services
- **HotRODAPIService**: Real API integration with Signadot routing header support
- **MockAPIService**: Mock service for testing enhanced features locally

### Views
- **HomeView**: Main interface with location selection, driver selection, and booking
- **EnvironmentSelectorView**: Debug panel for switching between environments
- **TripInfoView**: Comprehensive trip details with status management
- **RatingView**: Post-trip rating interface

## 🧪 Testing Scenarios

### 1. Fast ETA Feature (Route Service)
**Sandbox**: `route-fast-eta`
- **Test**: ETA calculations in seconds instead of minutes
- **Expected**: Drivers show "2500 sec", "1880 sec" instead of "8 min", "5 min"
- **Validation**: Compare with production baseline (ETA in minutes)

### 2. SD License Plate Feature (Driver Service)
**Sandbox**: `driver-sd-license`
- **Test**: License plates with "SD-" prefix for Signadot branding
- **Expected**: License plates show "SD-T712345C" instead of "T712345C"
- **Validation**: Production shows standard license plates without prefix

### 3. Combined Features
**Sandbox**: `combined-features`
- **Test**: Both fast ETA AND SD license plates together
- **Expected**: ETA in seconds + SD- prefixed license plates
- **Validation**: Full feature integration testing

### 4. Combined RouteGroup
**RouteGroup**: `combined-features-routegroup`
- **Test**: Advanced routing with both features
- **Expected**: Same as combined but with enhanced traffic management
- **Validation**: Advanced routing capabilities demonstration

## 🚦 Usage Instructions

### 1. Enable Debug Mode
- Tap the wrench icon in the top-right corner
- Debug panel appears with environment selector

### 2. Select Testing Environment
- **🏭 Production (Baseline)**: Standard HotROD functionality (ETA in minutes, standard license plates)
- **📦 route-fast-eta**: Test fast ETA feature (ETA in seconds)
- **📦 driver-sd-license**: Test SD license plate feature (SD- prefix)
- **📦 combined-features**: Test both features together
- **📦 combined-features-routegroup**: Test advanced routing with both features

### 3. Book a Ride
1. Select pickup location
2. Select dropoff location
3. Enter your name
4. Choose a driver (note ETA format and license plates based on environment)
5. Tap "Book Ride"

### 4. Manage Trip
- View trip details with comprehensive information
- Start trip when ready
- Complete trip and provide rating

## 🔗 Signadot Integration

### Routing Headers
The app automatically injects Signadot routing headers when a sandbox is selected:
```swift
"baggage": "sd-routing-key=\(routingKey)"
"ot-baggage-sd-routing-key": routingKey
```

### Environment Configuration
```swift
// Production (no routing key)
baseURL: "http://localhost:8080"
routingHeaders: [:]

// Sandbox (with routing key)
baseURL: "http://localhost:8080"
routingHeaders: [
    "baggage": "sd-routing-key=route-fast-eta-routing-key",
    "ot-baggage-sd-routing-key": "route-fast-eta-routing-key"
]
```

## 🛠️ Development Setup

### Prerequisites
- Xcode 15.0+
- iOS 17.0+
- HotROD backend running locally or accessible via network

### Configuration
1. Update `baseURL` in `AppState` to point to your HotROD frontend service
2. Configure routing keys to match your actual Signadot sandbox routing keys
3. For production use, replace `MockAPIService` with `HotRODAPIService`

### Real API Integration
To use real HotROD APIs instead of mock data:

```swift
// In HomeViewModel.updateAPIService()
self.apiService = HotRODAPIService(
    baseURL: appState.baseURL, 
    routingHeaders: appState.routingHeaders
)
```

## 🎯 Key Benefits

### For Mobile Developers
- **Isolated Testing**: Test backend changes without affecting other developers
- **Feature Validation**: Validate new features before production deployment
- **Integration Testing**: Test multiple backend changes together
- **Rapid Iteration**: Quick feedback loop for backend API changes

### For Backend Developers
- **Mobile Validation**: Get mobile app feedback on API changes
- **User Experience Testing**: See how changes affect real user workflows
- **Cross-team Collaboration**: Enable mobile team to test backend PRs

### For QA Teams
- **Comprehensive Testing**: Test individual features and combinations
- **Regression Testing**: Compare new features against production baseline
- **User Journey Testing**: End-to-end testing with real mobile interface

## 🚀 Next Steps

1. **Real API Integration**: Connect to actual HotROD backend services
2. **Signadot API Integration**: Dynamically load available sandboxes from Signadot API
3. **Enhanced Error Handling**: Add comprehensive error states and retry mechanisms
4. **Offline Support**: Cache data for offline testing scenarios
5. **Analytics Integration**: Track feature usage and performance metrics

## 📝 Notes

- Currently uses mock data to demonstrate features - replace with real API calls for production
- Routing keys are hardcoded - integrate with Signadot API for dynamic loading
- Designed for local testing with port forwarding or direct network access to HotROD services

This iOS app provides a comprehensive testing platform for HotROD microservices using Signadot sandboxes, enabling mobile developers to validate backend changes in isolation with a beautiful, modern interface.
