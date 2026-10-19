// Standalone settings for the 26.2 port build.
//
// The repository's own settings.gradle.kts wires the per-version preprocessor
// subprojects (1.21, 1.21.1, 1.21.11). The 26.2 port compiles a single
// pre-generated tree instead, so it runs with its own settings file and never
// touches that wiring.
pluginManagement {
    repositories {
        maven("https://maven.fabricmc.net")
        mavenCentral()
        gradlePluginPortal()
    }
}

rootProject.name = "unionclef"
