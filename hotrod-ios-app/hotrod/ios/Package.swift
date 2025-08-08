// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HotRodApp",
    platforms: [
        .iOS(.v17)
    ],
    products: [
        .library(
            name: "HotRodApp",
            targets: ["HotRodApp"]),
    ],
    dependencies: [
        // Add any external dependencies here if needed
    ],
    targets: [
        .target(
            name: "HotRodApp",
            dependencies: []),
        .testTarget(
            name: "HotRodAppTests",
            dependencies: ["HotRodApp"]),
    ]
)
