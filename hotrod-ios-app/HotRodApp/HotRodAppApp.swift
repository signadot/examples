//
//  HotRodAppApp.swift
//  HotRodApp
//
//  Created by Raafat, Mostafa on 29/07/2025.
//

import SwiftUI

@main
struct HotRodAppApp: App {
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
        }
    }
}
