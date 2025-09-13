import Foundation

// MARK: - Environment & Sandbox Support
struct EnvironmentOption: Identifiable, Equatable {
    let id = UUID()
    let displayName: String
    let routingKey: String?
    let type: EnvironmentType
    let isCustom: Bool
    
    enum EnvironmentType {
        case production
        case sandbox
        case routeGroup
    }
    
    static let production = EnvironmentOption(
        displayName: "Production (Baseline)",
        routingKey: nil,
        type: .production,
        isCustom: false
    )
    
    static func customSandbox(routingKey: String) -> EnvironmentOption {
        return EnvironmentOption(
            displayName: "Custom Sandbox",
            routingKey: routingKey,
            type: .sandbox,
            isCustom: true
        )
    }
}

// MARK: - HotROD Backend Models
struct LocationResponse: Codable {
    let locations: [String]
}

struct SplashResponse: Codable {
    let Locations: [HotRODLocation]
    let TitleSuffix: String
}

struct HotRODLocation: Codable {
    let id: Int
    let name: String
    let coordinates: String
}

struct Driver: Codable, Identifiable {
    let id: String
    let name: String
    let location: String
    let eta: Int
    let rating: Double?
    let completedTrips: Int?
    let licensePlate: String?
    let etaUnit: String?
    
    var displayName: String {
        if let rating = rating, let trips = completedTrips {
            return "\(name) ⭐\(String(format: "%.1f", rating)) (\(trips) trips)"
        }
        return name
    }
    
    var etaText: String {
        if let unit = etaUnit {
            return "\(eta) \(unit)"
        } else {
            return "\(eta)"
        }
    }
    
    var licensePlateText: String {
        return licensePlate ?? "N/A"
    }
}

struct DriverResponse: Codable {
    let drivers: [Driver]
}

struct RideRequest: Codable {
    let SessionID: UInt
    let RequestID: UInt
    let PickupLocationID: UInt
    let DropoffLocationID: UInt
    
    // Helper initializer for easier creation
    init(sessionID: UInt, requestID: UInt, pickupLocationID: UInt, dropoffLocationID: UInt) {
        self.SessionID = sessionID
        self.RequestID = requestID
        self.PickupLocationID = pickupLocationID
        self.DropoffLocationID = dropoffLocationID
    }
}

struct RideResponse: Codable {
    let rideId: String
    let eta: Double
    let driverId: String
}

// MARK: - Trip Management
struct Trip: Codable, Identifiable, Hashable {
    let id: UUID
    let rideId: String?
    let customerName: String
    let pickupAddress: String
    let dropoffAddress: String
    let selectedDriver: Driver?
    let eta: TimeInterval
    var status: TripStatus
    
    enum TripStatus: String, Codable, CaseIterable {
        case booking = "Booking"
        case confirmed = "Confirmed"
        case driverEnRoute = "Driver En Route"
        case inProgress = "In Progress"
        case completed = "Completed"
        case cancelled = "Cancelled"
        
        var icon: String {
            switch self {
            case .booking: return "clock"
            case .confirmed: return "checkmark.circle"
            case .driverEnRoute: return "car"
            case .inProgress: return "location"
            case .completed: return "checkmark.circle.fill"
            case .cancelled: return "xmark.circle"
            }
        }
        
        var color: String {
            switch self {
            case .booking: return "orange"
            case .confirmed: return "blue"
            case .driverEnRoute: return "purple"
            case .inProgress: return "green"
            case .completed: return "green"
            case .cancelled: return "red"
            }
        }
    }
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    
    static func == (lhs: Trip, rhs: Trip) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Rating
struct Rating: Codable {
    var stars: Int
    var comment: String?
    let tripId: UUID
}

// MARK: - App State
class AppState: ObservableObject {
    @Published var selectedEnvironment: EnvironmentOption = .production
    @Published var availableEnvironments: [EnvironmentOption] = [.production]
    @Published var isDebugModeEnabled: Bool = false
    @Published var currentTrip: Trip?
    @Published var customRoutingKey: String = ""
    @Published var showingCustomSandboxInput: Bool = false
    
    var baseURL: String {
        // For local testing with signadot local connect
        // This uses the service DNS name that signadot local connect maps to /etc/hosts
        return "https://frontend.hotrod:8080"
    }
    
    var routingHeaders: [String: String] {
        guard let routingKey = selectedEnvironment.routingKey else {
            return [:]
        }
        
        // Use OpenTelemetry standard headers for Signadot routing
        // Reference: https://www.signadot.com/docs/guides/set-up-context-propagation#header-propagation
        return [
            "baggage": "sd-routing-key=\(routingKey)",
            "tracestate": "sd-routing-key=\(routingKey)"
        ]
    }
}
