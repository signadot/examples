import SwiftUI

struct RatingView: View {
    @StateObject private var viewModel: RatingViewModel
    @Environment(\.dismiss) private var dismiss
    
    init(tripId: UUID) {
        _viewModel = StateObject(wrappedValue: RatingViewModel(tripId: tripId))
    }
    
    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 20) {
                // Trip Info Header
                HStack {
                    Image(systemName: "car.fill")
                        .font(.system(size: 24))
                    VStack(alignment: .leading) {
                        Text("Trip Rating")
                            .font(.headline)
                        Text("Please rate your experience")
                            .font(.subheadline)
                            .foregroundColor(.gray)
                    }
                }
                .padding()
                
                // Feedback State
                if let feedbackState = viewModel.feedbackState {
                    switch feedbackState {
                    case .loading:
                        ProgressView()
                            .progressViewStyle(.circular)
                            .padding()
                    case .success:
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text("Rating submitted successfully!")
                                .foregroundColor(.green)
                        }
                        .padding()
                    case .error(let message):
                        VStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.red)
                            Text(message)
                                .foregroundColor(.red)
                        }
                        .padding()
                    }
                }
                
                // Rating Stars
                HStack(spacing: 10) {
                    ForEach(1...5, id: \.self) { index in
                        Button {
                            viewModel.rating.stars = index
                        } label: {
                            Image(systemName: viewModel.rating.stars >= index ? "star.fill" : "star")
                                .font(.system(size: 30))
                                .foregroundColor(viewModel.rating.stars >= index ? .yellow : .gray)
                        }
                    }
                }
                .padding()
                
                // Comment Field
                TextEditor(text: Binding(
                    get: { viewModel.rating.comment ?? "" },
                    set: { viewModel.rating.comment = $0.isEmpty ? nil : $0 }
                ))
                    .frame(height: 100)
                    .cornerRadius(8)
                    .padding()
                
                // Submit Button
                Button(action: viewModel.submitRating) {
                    Text(viewModel.feedbackState == .loading ? "Submitting..." : "Submit Rating")
                        .frame(maxWidth: .infinity)
                        .padding()
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.feedbackState == .loading)
                .padding()
                
                Spacer()
            }
            .navigationTitle("Rate Your Trip")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .onChange(of: viewModel.shouldDismiss) {
                if viewModel.shouldDismiss {
                    dismiss()
                }
            }
        }
    }
}

final class RatingViewModel: ObservableObject {
    @Published var rating: Rating
    @Published var feedbackState: FeedbackState?
    @Published var shouldDismiss = false
    private let apiService: APIService
    
    enum FeedbackState: Equatable {
        case success
        case error(String)
        case loading
    }
    
    init(tripId: UUID) {
        self.rating = Rating(stars: 0, comment: nil, tripId: tripId)
        // Use mock service for now - in production, get from environment
        self.apiService = MockAPIService(simulateEnhancedFeatures: true)
    }
    
    func submitRating() {
        feedbackState = .loading
        Task {
            do {
                try await apiService.submitRating(rating)
                await MainActor.run {
                    feedbackState = .success
                }
                // After a brief delay, trigger dismiss
                try await Task.sleep(nanoseconds: 1_500_000_000) // 1.5 seconds
                await MainActor.run {
                    shouldDismiss = true
                }
            } catch {
                await MainActor.run {
                    feedbackState = .error("Failed to submit rating: \(error.localizedDescription)")
                }
            }
        }
    }
}

#Preview {
    RatingView(tripId: UUID())
}
