import SwiftUI

extension Notification.Name {
    static let environmentChanged = Notification.Name("environmentChanged")
}

struct EnvironmentSelectorView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = EnvironmentSelectorViewModel()
    @State private var customRoutingKey = ""
    @State private var showingCustomInput = false
    
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
                
                Button("🧪 Custom Sandbox...") {
                    showingCustomInput = true
                }
                
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
        .sheet(isPresented: $showingCustomInput) {
            CustomSandboxInputView(
                routingKey: $customRoutingKey,
                onSave: { key in
                    let customEnvironment = EnvironmentOption.customSandbox(routingKey: key)
                    appState.selectedEnvironment = customEnvironment
                    viewModel.updateAPIService(for: customEnvironment)
                    NotificationCenter.default.post(name: .environmentChanged, object: customEnvironment)
                    showingCustomInput = false
                }
            )
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
        
        // Only show Production - Custom Sandbox is accessed via menu option
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            appState.availableEnvironments = [.production]
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

// MARK: - Custom Sandbox Input View
struct CustomSandboxInputView: View {
    @Binding var routingKey: String
    let onSave: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Sandbox Routing Key")
                        .font(.headline)
                        .fontWeight(.medium)
                    
                    Text("Enter the routing key for your Signadot sandbox. You can find this in your sandbox configuration or Signadot dashboard.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Routing Key")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    TextField("e.g., 1yvv6z86yc060", text: $routingKey)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Examples:")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("• Driver Ratings:")
                                .font(.caption)
                            Text("62g6dy259mmmj")
                                .font(.caption.monospaced())
                                .foregroundColor(.blue)
                        }
                        
                        HStack {
                            Text("• Location Enhanced:")
                                .font(.caption)
                            Text("1yvv6z86yc060")
                                .font(.caption.monospaced())
                                .foregroundColor(.blue)
                        }
                    }
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("Custom Sandbox")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Connect") {
                        onSave(routingKey.trimmingCharacters(in: .whitespacesAndNewlines))
                    }
                    .disabled(routingKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}

#Preview {
    EnvironmentSelectorView()
        .environmentObject(AppState())
}
