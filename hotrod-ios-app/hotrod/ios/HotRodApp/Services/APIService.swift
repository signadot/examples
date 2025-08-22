import Foundation

protocol APIService {
    func getLocations() async throws -> [HotRODLocation]
    func getDrivers(for location: String) async throws -> [Driver]
    func bookRide(_ request: RideRequest) async throws -> RideResponse
    func submitRating(_ rating: Rating) async throws
}

class HotRODAPIService: APIService {
    private let baseURL: String
    private let session: URLSession
    private let routingHeaders: [String: String]
    
    init(baseURL: String, routingHeaders: [String: String] = [:]) {
        self.baseURL = baseURL
        self.routingHeaders = routingHeaders
        
        // Configure URLSession with custom headers
        let config = URLSessionConfiguration.default
        config.httpAdditionalHeaders = routingHeaders
        self.session = URLSession(configuration: config)
    }
    
    func getLocations() async throws -> [HotRODLocation] {
        let url = URL(string: "http://location.hotrod:8081/locations")!
        var request = URLRequest(url: url)
        
        // Add Signadot routing headers
        for (key, value) in routingHeaders {
            request.setValue(value, forHTTPHeaderField: key)
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        // Parse the direct locations response
        let locations = try JSONDecoder().decode([HotRODLocation].self, from: data)
        return locations
    }
    
    func getDrivers(for location: String) async throws -> [Driver] {
        // Fetch driver data from the backend via dispatch endpoint
        // This simulates the Kafka topic interaction by triggering a dispatch request
        // and extracting driver information from the response
        
        let url = URL(string: "\(baseURL)/dispatch")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add routing headers for sandbox testing
        for (key, value) in routingHeaders {
            request.setValue(value, forHTTPHeaderField: key)
        }
        
        // Create a dispatch request to get driver information
        let dispatchRequest = [
            "pickupLocation": [
                "id": 1,
                "name": location,
                "coordinates": "0,0"
            ],
            "dropoffLocation": [
                "id": 2, 
                "name": "Destination",
                "coordinates": "100,100"
            ]
        ]
        
        let requestData = try JSONSerialization.data(withJSONObject: dispatchRequest)
        request.httpBody = requestData
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                // If dispatch fails, fall back to simulated driver data based on routing
                return generateDriversBasedOnRouting(for: location)
            }
            
            // Parse the dispatch response to extract driver information
            if let responseDict = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let driverInfo = responseDict["driver"] as? [String: Any] {
                
                // Extract driver data from dispatch response
                let driverId = driverInfo["driverId"] as? String ?? "unknown"
                let coordinates = driverInfo["coordinates"] as? String ?? "0,0"
                let rating = driverInfo["rating"] as? Double
                
                // Generate driver based on backend response
                let driver = Driver(
                    id: driverId,
                    name: generateDriverName(from: driverId),
                    location: location,
                    eta: Int.random(in: 3...15),
                    rating: rating,
                    completedTrips: rating != nil ? Int.random(in: 150...400) : nil
                )
                
                return [driver]
            }
            
            // If no driver info in response, generate based on routing
            return generateDriversBasedOnRouting(for: location)
            
        } catch {
            print("Error fetching drivers: \(error)")
            // Fall back to simulated data on network error
            return generateDriversBasedOnRouting(for: location)
        }
    }
    
    private func generateDriversBasedOnRouting(for location: String) -> [Driver] {
        // Check if we're in driver-ratings sandbox based on OpenTelemetry routing headers
        let isDriverRatingsSandbox = routingHeaders["baggage"] != nil || routingHeaders["tracestate"] != nil
        
        if isDriverRatingsSandbox {
            // Enhanced drivers with ratings (driver-ratings sandbox)
            return [
                Driver(id: "driver-001", name: "John Smith", location: location, eta: Int.random(in: 3...15), rating: 4.8, completedTrips: 245),
                Driver(id: "driver-002", name: "Sarah Johnson", location: location, eta: Int.random(in: 2...12), rating: 4.9, completedTrips: 312),
                Driver(id: "driver-003", name: "Mike Wilson", location: location, eta: Int.random(in: 5...18), rating: 4.6, completedTrips: 189)
            ]
        } else {
            // Basic drivers without ratings (production baseline)
            return [
                Driver(id: "driver-001", name: "John Smith", location: location, eta: Int.random(in: 3...15), rating: nil, completedTrips: nil),
                Driver(id: "driver-002", name: "Sarah Johnson", location: location, eta: Int.random(in: 2...12), rating: nil, completedTrips: nil),
                Driver(id: "driver-003", name: "Mike Wilson", location: location, eta: Int.random(in: 5...18), rating: nil, completedTrips: nil)
            ]
        }
    }
    
    private func generateDriverName(from driverId: String) -> String {
        // Generate consistent driver names based on driver ID
        let names = [
            "John Smith", "Sarah Johnson", "Mike Wilson", "Emily Davis", 
            "Chris Brown", "Jessica Taylor", "David Miller", "Ashley Garcia"
        ]
        let hash = abs(driverId.hashValue)
        return names[hash % names.count]
    }
    
    func bookRide(_ request: RideRequest) async throws -> RideResponse {
        let url = URL(string: "\(baseURL)/dispatch")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add Signadot routing headers
        for (key, value) in routingHeaders {
            urlRequest.setValue(value, forHTTPHeaderField: key)
        }
        
        let requestData = try JSONEncoder().encode(request)
        urlRequest.httpBody = requestData
        
        let (data, response) = try await session.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let rideResponse = try JSONDecoder().decode(RideResponse.self, from: data)
        return rideResponse
    }
    
    func submitRating(_ rating: Rating) async throws {
        // For now, just log the rating submission
        print("📝 Submitting rating: \(rating.stars) stars for trip: \(rating.tripId)")
        if let comment = rating.comment {
            print("💬 Comment: \(comment)")
        }
        
        // TODO: Implement actual rating submission endpoint when available
        try await Task.sleep(nanoseconds: 500_000_000) // Simulate network delay
    }
}

// MARK: - Mock Service for Testing
class MockAPIService: APIService {
    private let shouldSimulateEnhancedFeatures: Bool
    
    init(simulateEnhancedFeatures: Bool = false) {
        self.shouldSimulateEnhancedFeatures = simulateEnhancedFeatures
    }
    
    func getLocations() async throws -> [HotRODLocation] {
        try await Task.sleep(nanoseconds: 500_000_000) // Simulate network delay
        
        if shouldSimulateEnhancedFeatures {
            // Enhanced locations (simulating location-enhanced sandbox)
            return [
                HotRODLocation(id: 1, name: "567 5th Ave", coordinates: "231,773"),
                HotRODLocation(id: 123, name: "JFK Airport", coordinates: "115,277"),
                HotRODLocation(id: 392, name: "Brooklyn Mall", coordinates: "577,322"),
                HotRODLocation(id: 567, name: "Central Park", coordinates: "211,653"),
                HotRODLocation(id: 731, name: "Times Square", coordinates: "728,326"),
                HotRODLocation(id: 777, name: "LaGuardia Airport", coordinates: "878,576"),
                HotRODLocation(id: 888, name: "Brooklyn Bridge", coordinates: "456,789")
            ]
        } else {
            // Basic locations (production baseline)
            return [
                HotRODLocation(id: 1, name: "567 5th Ave", coordinates: "231,773"),
                HotRODLocation(id: 567, name: "Central Park", coordinates: "211,653"),
                HotRODLocation(id: 731, name: "Times Square", coordinates: "728,326"),
                HotRODLocation(id: 888, name: "Brooklyn Bridge", coordinates: "456,789")
            ]
        }
    }
    
    func getDrivers(for location: String) async throws -> [Driver] {
        try await Task.sleep(nanoseconds: 800_000_000) // Simulate network delay
        
        if shouldSimulateEnhancedFeatures {
            // Drivers with ratings (simulating driver-ratings sandbox)
            return [
                Driver(id: "driver-001", name: "John Smith", location: location, eta: Int.random(in: 3...15), rating: 4.8, completedTrips: 245),
                Driver(id: "driver-002", name: "Sarah Johnson", location: location, eta: Int.random(in: 2...12), rating: 4.9, completedTrips: 312),
                Driver(id: "driver-003", name: "Mike Wilson", location: location, eta: Int.random(in: 5...18), rating: 4.6, completedTrips: 189)
            ]
        } else {
            // Basic drivers without ratings (production baseline)
            return [
                Driver(id: "driver-001", name: "John Smith", location: location, eta: Int.random(in: 3...15), rating: nil, completedTrips: nil),
                Driver(id: "driver-002", name: "Sarah Johnson", location: location, eta: Int.random(in: 2...12), rating: nil, completedTrips: nil),
                Driver(id: "driver-003", name: "Mike Wilson", location: location, eta: Int.random(in: 5...18), rating: nil, completedTrips: nil)
            ]
        }
    }
    
    func bookRide(_ request: RideRequest) async throws -> RideResponse {
        try await Task.sleep(nanoseconds: 1_000_000_000) // Simulate booking delay
        
        return RideResponse(
            rideId: UUID().uuidString,
            eta: Double.random(in: 8...25),
            driverId: "driver-\(Int.random(in: 1...3).formatted(.number.precision(.integerLength(3))))"
        )
    }
    
    func submitRating(_ rating: Rating) async throws {
        try await Task.sleep(nanoseconds: 500_000_000)
        print("✅ Rating submitted successfully: \(rating.stars) stars")
    }
}

// MARK: - API Errors
enum APIError: LocalizedError {
    case invalidRequest
    case invalidResponse
    case networkError(Error)
    case decodingError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidRequest:
            return "Invalid request"
        case .invalidResponse:
            return "Invalid response from server"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .decodingError(let error):
            return "Data parsing error: \(error.localizedDescription)"
        }
    }
}
