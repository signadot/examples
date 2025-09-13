//
//  ContentView.swift
//  HotRodApp
//
//  Created by Raafat, Mostafa on 29/07/2025.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            HomeView()
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}
