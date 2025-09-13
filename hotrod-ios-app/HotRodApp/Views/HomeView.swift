import SwiftUI

struct HomeView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = HomeViewModel()
    @State private var showingDebugPanel = false
    
    var body: some View {
        NavigationStack(path: $viewModel.navigationPath) {
            ScrollView {
                VStack(spacing: 24) {
                    // Header Section
                    headerSection
                    
                    // Debug Panel (collapsible)
                    if appState.isDebugModeEnabled {
                        debugPanel
                    }
                    
                    // Main Booking Interface
                    bookingSection
                    
                    // Current Trip Status
                    if let trip = appState.currentTrip {
                        currentTripSection(trip)
                    }
                }
                .padding()
            }
            .navigationTitle("🚗 HotROD")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { appState.isDebugModeEnabled.toggle() }) {
                        Image(systemName: appState.isDebugModeEnabled ? "wrench.fill" : "wrench")
                            .foregroundColor(appState.isDebugModeEnabled ? .orange : .gray)
                    }
                }
            }
            .navigationDestination(for: Trip.self) { trip in
                TripInfoView(trip: trip)
            }
            .environmentObject(appState)
            .onAppear {
                viewModel.setupWith(appState: appState)
            }
            .onReceive(NotificationCenter.default.publisher(for: .environmentChanged)) { _ in
                viewModel.updateAPIService()
                viewModel.loadLocations()
                // Clear current selections when switching environments
                viewModel.selectedPickupLocation = nil
                viewModel.selectedDropoffLocation = nil
                viewModel.selectedDriver = nil
                viewModel.availableDrivers = []
            }
        }
    }
    
    // MARK: - Header Section
    private var headerSection: some View {
        VStack(spacing: 16) {
            // App Title with Icon
            HStack {
                Image(systemName: "car.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(.linearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing))
                
                VStack(alignment: .leading) {
                    Text("HotROD Mobile")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("Book your ride")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        }
    }
    
    // MARK: - Debug Panel
    private var debugPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "wrench.fill")
                    .foregroundColor(.orange)
                Text("Developer Mode")
                    .font(.headline)
                    .foregroundColor(.orange)
                Spacer()
            }
            
            EnvironmentSelectorView()
                .environmentObject(appState)
            
            Text("Environment: \(appState.selectedEnvironment.displayName)")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.orange.opacity(0.1))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.orange.opacity(0.3), lineWidth: 1)
        )
    }
    
    // MARK: - Booking Section
    private var bookingSection: some View {
        VStack(spacing: 20) {
            // Location Selection
            locationSelectionSection
            
            // Customer Name Input
            customerNameSection
            
            // Driver Selection (if available)
            if !viewModel.availableDrivers.isEmpty {
                driverSelectionSection
            }
            
            // Book Ride Button
            bookRideButton
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    private var locationSelectionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Where to?")
                .font(.headline)
                .foregroundColor(.primary)
            
            // Pickup Location
            VStack(alignment: .leading, spacing: 8) {
                Text("Pickup Location")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Menu {
                    ForEach(viewModel.availableLocations, id: \.id) { location in
                        Button(location.name) {
                            viewModel.selectedPickupLocation = location
                            viewModel.loadDrivers()
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "location.circle.fill")
                            .foregroundColor(.green)
                        Text(viewModel.selectedPickupLocation?.name ?? "Select pickup location")
                            .foregroundColor(viewModel.selectedPickupLocation != nil ? .primary : .secondary)
                        Spacer()
                        Image(systemName: "chevron.down")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
            }
            
            // Dropoff Location
            VStack(alignment: .leading, spacing: 8) {
                Text("Dropoff Location")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Menu {
                    ForEach(viewModel.availableLocations, id: \.id) { location in
                        Button(location.name) {
                            viewModel.selectedDropoffLocation = location
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "location.circle.fill")
                            .foregroundColor(.red)
                        Text(viewModel.selectedDropoffLocation?.name ?? "Select dropoff location")
                            .foregroundColor(viewModel.selectedDropoffLocation != nil ? .primary : .secondary)
                        Spacer()
                        Image(systemName: "chevron.down")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
            }
        }
    }
    
    private var customerNameSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Your Name")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            TextField("Enter your name", text: $viewModel.customerName)
                .textFieldStyle(.roundedBorder)
        }
    }
    
    private var driverSelectionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Available Drivers")
                .font(.headline)
            
            if viewModel.isLoadingDrivers {
                HStack {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text("Finding drivers...")
                        .foregroundColor(.secondary)
                }
                .padding()
            } else {
                LazyVStack(spacing: 8) {
                    ForEach(viewModel.availableDrivers) { driver in
                        DriverRowView(driver: driver, isSelected: viewModel.selectedDriver?.id == driver.id) {
                            viewModel.selectedDriver = driver
                        }
                    }
                }
            }
        }
    }
    
    private var bookRideButton: some View {
        Button(action: viewModel.bookRide) {
            HStack {
                if viewModel.isBookingRide {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.8)
                } else {
                    Image(systemName: "car.fill")
                }
                Text(viewModel.isBookingRide ? "Booking..." : "Book Ride")
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(
                LinearGradient(
                    colors: viewModel.canBookRide ? [.blue, .purple] : [.gray],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .foregroundColor(.white)
            .cornerRadius(12)
        }
        .disabled(!viewModel.canBookRide || viewModel.isBookingRide)
    }
    
    // MARK: - Current Trip Section
    private func currentTripSection(_ trip: Trip) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: trip.status.icon)
                    .foregroundColor(Color(trip.status.color))
                Text("Current Trip")
                    .font(.headline)
                Spacer()
                Text(trip.status.rawValue)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(trip.status.color).opacity(0.2))
                    .cornerRadius(8)
            }
            
            VStack(alignment: .leading, spacing: 4) {
                Text("From: \(trip.pickupAddress)")
                Text("To: \(trip.dropoffAddress)")
                if let driver = trip.selectedDriver {
                    Text("Driver: \(driver.displayName)")
                }
            }
            .font(.subheadline)
            .foregroundColor(.secondary)
            
            Button("View Trip Details") {
                viewModel.navigationPath.append(trip)
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
}

// MARK: - Driver Row View
struct DriverRowView: View {
    let driver: Driver
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack {
                Image(systemName: "person.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.blue)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(driver.name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    HStack(spacing: 8) {
                        if let rating = driver.rating, let trips = driver.completedTrips {
                            Text("⭐ \(String(format: "%.1f", rating)) • \(trips) trips")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        // Show license plate for demo
                        Text("🚗 \(driver.licensePlateText)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text(driver.etaText)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text("ETA")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                }
            }
            .padding()
            .background(isSelected ? Color.blue.opacity(0.1) : Color(.systemGray6))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - View Model
final class HomeViewModel: ObservableObject {
    @Published var navigationPath = NavigationPath()
    @Published var availableLocations: [HotRODLocation] = []
    @Published var availableDrivers: [Driver] = []
    @Published var selectedPickupLocation: HotRODLocation?
    @Published var selectedDropoffLocation: HotRODLocation?
    @Published var selectedDriver: Driver?
    @Published var customerName: String = ""
    @Published var isLoadingDrivers = false
    @Published var isBookingRide = false
    
    private var apiService: APIService?
    private var appState: AppState?
    
    var canBookRide: Bool {
        selectedPickupLocation != nil &&
        selectedDropoffLocation != nil &&
        !customerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        selectedDriver != nil
    }
    
    func setupWith(appState: AppState) {
        self.appState = appState
        updateAPIService()
        loadLocations()
    }
    
    func updateAPIService() {
        guard let appState = appState else { return }
        
        // Use real HotROD API service with routing headers based on selected environment
        let routingHeaders = appState.routingHeaders
        self.apiService = HotRODAPIService(
            baseURL: appState.baseURL,
            routingHeaders: routingHeaders
        )
    }
    
    func loadLocations() {
        guard let apiService = apiService else { return }
        
        Task {
            do {
                let locations = try await apiService.getLocations()
                await MainActor.run {
                    self.availableLocations = locations
                }
            } catch {
                print("Error loading locations: \(error)")
            }
        }
    }
    
    func loadDrivers() {
        guard let apiService = apiService,
              let location = selectedPickupLocation else { return }
        
        isLoadingDrivers = true
        
        Task {
            do {
                let drivers = try await apiService.getDrivers(for: location.name)
                await MainActor.run {
                    self.availableDrivers = drivers
                    self.isLoadingDrivers = false
                }
            } catch {
                await MainActor.run {
                    self.isLoadingDrivers = false
                }
                print("Error loading drivers: \(error)")
            }
        }
    }
    
    func bookRide() {
        guard let apiService = apiService,
              let pickup = selectedPickupLocation,
              let dropoff = selectedDropoffLocation,
              let driver = selectedDriver,
              !customerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        
        isBookingRide = true
        
        Task {
            do {
                let request = RideRequest(
                    sessionID: UInt.random(in: 1...1000),
                    requestID: UInt.random(in: 1...10000),
                    pickupLocationID: UInt(pickup.id),
                    dropoffLocationID: UInt(dropoff.id)
                )
                
                let response = try await apiService.bookRide(request)
                
                let trip = Trip(
                    id: UUID(),
                    rideId: response.rideId,
                    customerName: customerName.trimmingCharacters(in: .whitespacesAndNewlines),
                    pickupAddress: pickup.name,
                    dropoffAddress: dropoff.name,
                    selectedDriver: driver,
                    eta: response.eta,
                    status: .confirmed
                )
                
                await MainActor.run {
                    self.appState?.currentTrip = trip
                    self.isBookingRide = false
                    self.navigationPath.append(trip)
                }
            } catch {
                await MainActor.run {
                    self.isBookingRide = false
                }
                print("Error booking ride: \(error)")
            }
        }
    }
}

#Preview {
    HomeView()
        .environmentObject(AppState())
}
