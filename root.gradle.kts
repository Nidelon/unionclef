plugins {
    id("net.fabricmc.fabric-loom") version "1.17.14" apply false
}

subprojects {
    repositories {
        mavenCentral()
        maven("https://libraries.minecraft.net/")
        maven("https://repo.spongepowered.org/repository/maven-public/")
        maven("https://maven.fabricmc.net/")
        maven("https://jitpack.io")
        maven("https://babbaj.github.io/maven/")
    }
}

// Default MC version — root tasks (runClient, build, etc.) delegate here
val defaultVersion = "26.2"

listOf("compileJava", "runClient", "build", "remapJar", "processResources", "githubRelease", "githubPreRelease").forEach { taskName ->
    tasks.register(taskName) {
        dependsOn(":$defaultVersion:$taskName")
    }
}

