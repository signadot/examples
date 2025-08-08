import SwiftUI

extension Notification.Name {
    static let environmentChanged = Notification.Name("environmentChanged")
}

struct EnvironmentSelectorView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = EnvironmentSelectorViewModel()
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Test Environment")
                .font(.subheadline)
                .fontWeight(.medium)
            
            Menu {
                ForEach(appState.availableEnvironments) { environment in
                    Button(action: {
                        appState.selectedEnvironment = environment
                        viewModel.updateAPIService(for: environment)
                        // Trigger a refresh notification
                        NotificationCenter.default.post(name: .environmentChanged, object: environment)
                    }) {
                        HStack {
                            Text(environment.displayName)
                            if appState.selectedEnvironment.id == environment.id {
                                Spacer()
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
                
                Divider()
                
                Button("Refresh Environments") {
                    viewModel.loadAvailableEnvironments()
                }
            } label: {
                HStack {
                    environmentIcon
                    Text(appState.selectedEnvironment.displayName)
                        .foregroundColor(.primary)
                    Spacer()
                    Image(systemName: "chevron.down")
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            }
            
            if viewModel.isLoading {
                HStack {
                    ProgressView()
                        .scaleEffect(0.7)
                    Text("Loading environments...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .onAppear {
            viewModel.setup(with: appState)
        }
    }
    
    private var environmentIcon: some View {
        Group {
            switch appState.selectedEnvironment.type {
            case .production:
                Image(systemName: "building.2.fill")
                    .foregroundColor(.green)
            case .sandbox:
                Image(systemName: "cube.fill")
                    .foregroundColor(.blue)
            case .routeGroup:
                Image(systemName: "link")
                    .foregroundColor(.purple)
            }
        }
    }
}

// MARK: - View Model
class EnvironmentSelectorViewModel: ObservableObject {
    @Published var isLoading = false
    private var appState: AppState?
    
    func setup(with appState: AppState) {
        self.appState = appState
        loadAvailableEnvironments()
    }
    
    func loadAvailableEnvironments() {
        guard let appState = appState else { return }
        
        isLoading = true
        
        // Simulate loading sandbox environments
        // In a real implementation, you would call the Signadot API here
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            let mockEnvironments: [EnvironmentOption] = [
                .production,
                EnvironmentOption(
                    displayName: "🚗 driver-ratings - Driver service with ratings",
                    routingKey: "62g6dy259mmmj",
                    type: .sandbox
                ),
                EnvironmentOption(
                    displayName: "📍 location-enhanced",
                    routingKey: "1yvv6z86yc060",
                    type: .sandbox
                )
            ]
            
            appState.availableEnvironments = mockEnvironments
            self.isLoading = false
        }
    }
    
    func updateAPIService(for environment: EnvironmentOption) {
        // This would trigger the HomeViewModel to update its API service
        // with the new routing headers for the selected environment
        print("🔄 Switching to environment: \(environment.displayName)")
        if let routingKey = environment.routingKey {
            print("🏷️ Using routing key: \(routingKey)")
        }
    }
}

#Preview {
    EnvironmentSelectorView()
        .environmentObject(AppState())
}
