import SwiftUI

struct TripInfoView: View {
    @StateObject private var viewModel: TripInfoViewModel
    @Environment(\.dismiss) private var dismiss
    
    init(trip: Trip) {
        _viewModel = StateObject(wrappedValue: TripInfoViewModel(trip: trip))
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Trip Status Header
                tripStatusHeader
                
                // Customer & Driver Info
                customerDriverSection
                
                // Trip Details
                tripDetailsSection
                
                // Action Buttons
                actionButtonsSection
                
                Spacer(minLength: 50)
            }
            .padding()
        }
        .navigationTitle("Trip Details")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Done") {
                    dismiss()
                }
            }
        }
        .background(
            NavigationLink(
                destination: RatingView(tripId: viewModel.trip.id),
                isActive: $viewModel.shouldNavigateToRating
            ) {
                EmptyView()
            }
            .hidden()
        )
    }
    
    // MARK: - Trip Status Header
    private var tripStatusHeader: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: viewModel.trip.status.icon)
                    .font(.system(size: 32))
                    .foregroundColor(Color(viewModel.trip.status.color))
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(viewModel.trip.status.rawValue)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    if let rideId = viewModel.trip.rideId {
                        Text("Ride ID: \(rideId.prefix(8))...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("\(Int(viewModel.trip.eta / 60)) min")
                        .font(.title3)
                        .fontWeight(.semibold)
                    Text("ETA")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Customer & Driver Section
    private var customerDriverSection: some View {
        VStack(spacing: 16) {
            // Customer Info
            HStack {
                Image(systemName: "person.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.blue)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Customer")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(viewModel.trip.customerName)
                        .font(.headline)
                }
                
                Spacer()
            }
            
            // Driver Info (if available)
            if let driver = viewModel.trip.selectedDriver {
                Divider()
                
                HStack {
                    Image(systemName: "car.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.green)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Driver")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(driver.name)
                            .font(.headline)
                        
                        if let rating = driver.rating, let trips = driver.completedTrips {
                            Text("⭐ \(String(format: "%.1f", rating)) • \(trips) completed trips")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing) {
                        Text(viewModel.trip.selectedDriver?.etaText ?? "N/A")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        Text("Original ETA")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Trip Details Section
    private var tripDetailsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Trip Route")
                .font(.headline)
            
            VStack(spacing: 12) {
                // Pickup Location
                HStack {
                    Image(systemName: "location.circle.fill")
                        .foregroundColor(.green)
                        .font(.system(size: 20))
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Pickup")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(viewModel.trip.pickupAddress)
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    Spacer()
                }
                
                // Route Line
                HStack {
                    Rectangle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 2, height: 20)
                        .offset(x: 9)
                    Spacer()
                }
                
                // Dropoff Location
                HStack {
                    Image(systemName: "location.circle.fill")
                        .foregroundColor(.red)
                        .font(.system(size: 20))
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Dropoff")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(viewModel.trip.dropoffAddress)
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    Spacer()
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Action Buttons Section
    private var actionButtonsSection: some View {
        VStack(spacing: 12) {
            if viewModel.trip.status == .booking || viewModel.trip.status == .confirmed {
                Button(action: viewModel.startRide) {
                    HStack {
                        Image(systemName: "play.circle.fill")
                        Text("Start Trip")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
            } else if viewModel.trip.status == .driverEnRoute || viewModel.trip.status == .inProgress {
                Button(action: viewModel.endTrip) {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                        Text("Complete Trip")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
            } else if viewModel.trip.status == .completed {
                Button(action: { viewModel.shouldNavigateToRating = true }) {
                    HStack {
                        Image(systemName: "star.fill")
                        Text("Rate Trip")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.orange)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
            }
            
            if viewModel.trip.status != .completed && viewModel.trip.status != .cancelled {
                Button(action: viewModel.cancelTrip) {
                    HStack {
                        Image(systemName: "xmark.circle")
                        Text("Cancel Trip")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .foregroundColor(.red)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.red, lineWidth: 1)
                    )
                }
            }
        }
    }
}

final class TripInfoViewModel: ObservableObject {
    @Published var trip: Trip
    @Published var shouldNavigateToRating = false
    private let apiService: APIService
    
    init(trip: Trip) {
        self.trip = trip
        // Use mock service for now - in production, get from environment
        self.apiService = MockAPIService(simulateEnhancedFeatures: true)
    }
    
    func startRide() {
        Task {
            await MainActor.run {
                trip.status = .driverEnRoute
            }
            
            // Simulate driver arriving
            try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
            
            await MainActor.run {
                trip.status = .inProgress
            }
        }
    }
    
    func endTrip() {
        Task {
            await MainActor.run {
                trip.status = .completed
                shouldNavigateToRating = true
            }
        }
    }
    
    func cancelTrip() {
        Task {
            await MainActor.run {
                trip.status = .cancelled
            }
        }
    }
}

#Preview {
    TripInfoView(trip: Trip(
        id: UUID(),
        rideId: "ride-12345",
        customerName: "John Doe",
        pickupAddress: "Central Park",
        dropoffAddress: "Times Square",
        selectedDriver: Driver(
            id: "driver-001",
            name: "Sarah Johnson",
            location: "Central Park",
            eta: 8,
            rating: 4.9,
            completedTrips: 312,
            licensePlate: "T712345C",
            etaUnit: "min"
        ),
        eta: 15 * 60,
        status: .confirmed
    ))
}
