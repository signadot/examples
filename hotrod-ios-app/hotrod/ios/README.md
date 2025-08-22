# HotROD iOS App - Signadot Sandbox Testing

A modern, beautiful iOS app built with SwiftUI to test HotROD microservices using Signadot sandboxes. This app demonstrates how mobile developers can test backend changes in isolation before they reach production.

## 🚀 Features

### 🎯 Core Functionality
- **Ride Booking Interface**: Complete ride booking flow with location selection, driver selection, and trip management
- **Signadot Sandbox Integration**: Switch between production, sandbox, and route group environments
- **Enhanced Location Service Testing**: Test new pickup locations (airports, malls) via location-enhanced sandbox
- **Driver Ratings Feature Testing**: Test driver ratings and trip history via driver-ratings sandbox
- **Combined Feature Testing**: Test multiple features together using route groups

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

### 1. Enhanced Location Service
**Sandbox**: `location-enhanced`
- **Test**: New pickup locations (JFK Airport, Brooklyn Mall, LaGuardia Airport)
- **Expected**: Additional location options appear in pickup/dropoff menus
- **Validation**: Compare with production baseline (fewer locations)

### 2. Driver Ratings Feature
**Sandbox**: `driver-ratings`
- **Test**: Driver selection shows ratings and completed trips
- **Expected**: Drivers display "⭐ 4.8 (245 trips)" format
- **Validation**: Production shows drivers without ratings

### 3. Combined Features
**Route Group**: `combined-features`
- **Test**: Both enhanced locations AND driver ratings
- **Expected**: New locations + driver ratings work together
- **Validation**: Full feature integration testing

## 🚦 Usage Instructions

### 1. Enable Debug Mode
- Tap the wrench icon in the top-right corner
- Debug panel appears with environment selector

### 2. Select Testing Environment
- **🏭 Production (Baseline)**: Standard HotROD functionality
- **📦 driver-ratings**: Test driver ratings feature
- **📦 location-enhanced**: Test enhanced location service
- **🔗 combined-features**: Test both features together

### 3. Book a Ride
1. Select pickup location (note new options in enhanced mode)
2. Select dropoff location
3. Enter your name
4. Choose a driver (note ratings in enhanced mode)
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
    "baggage": "sd-routing-key=driver-ratings-routing-key",
    "ot-baggage-sd-routing-key": "driver-ratings-routing-key"
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
