//
//  HotRodAppApp.swift
//  HotRodApp
//
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
