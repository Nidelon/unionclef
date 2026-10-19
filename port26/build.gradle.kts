plugins {
    java
    id("net.fabricmc.fabric-loom") version "1.17.14"
}

// UnionClef base port: Minecraft 26.2 / Java 25 / Fabric.
// 26.x ships unobfuscated (official Mojang names), so there is deliberately NO
// mappings() declaration here - the source tree has been renamed yarn -> mojmap.

val mcVersion = "26.2"
val loaderVersion = "0.19.3"
val fabricApiVersion = "0.154.2+26.2"
val targetJava = 25

version = "0.95.58-26.2-port.1"
group = "dev.unionclef"

base {
    archivesName = "unionclef"
}

repositories {
    mavenCentral()
    maven {
        name = "babbaj"
        url = uri("https://babbaj.github.io/maven/")
    }
    maven {
        name = "maxhenkel"
        url = uri("https://maven.maxhenkel.de/repository/public")
    }
    maven {
        name = "sponge"
        url = uri("https://repo.spongepowered.org/repository/maven-public/")
    }
}

// `gradle runClient -PquickPlay=localhost:25565` drops straight into a world,
// which is how the port is smoke-tested on a headless display.
loom {
    runs {
        named("client") {
            val qp = project.findProperty("quickPlay") as String?
            if (qp != null) {
                programArgs("--quickPlayMultiplayer", qp)
            }
        }
    }
}

dependencies {
    minecraft("com.mojang:minecraft:$mcVersion")
    implementation("net.fabricmc:fabric-loader:$loaderVersion")
    implementation("net.fabricmc.fabric-api:fabric-api:$fabricApiVersion")

    // MixinExtras
    annotationProcessor("io.github.llamalad7:mixinextras-fabric:0.3.5")
    implementation("io.github.llamalad7:mixinextras-fabric:0.3.5")

    // JSON
    implementation("com.fasterxml.jackson.core:jackson-core:2.17.2")
    implementation("com.fasterxml.jackson.core:jackson-annotations:2.17.2")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.17.2")

    // jsr305: the 26.2 jar carries @Immutable on some classes, so the annotation
    // has to be on the compile classpath or javac refuses to read them
    compileOnly("com.google.code.findbugs:jsr305:3.0.2")

    // Nether pathfinder
    implementation("dev.babbaj:nether-pathfinder:1.5")

    // Voice chat API (compile-time only)
    compileOnly("de.maxhenkel.voicechat:voicechat-api:2.6.0")

    // Python bridge
    implementation("net.sf.py4j:py4j:0.10.9.7")
}

java {
    toolchain.languageVersion = JavaLanguageVersion.of(targetJava)
}

// ---------------------------------------------------------------------------
// Source pipeline:  src/ (canonical, directive-carrying, yarn names)
//                     -> scripts/port/preprocess.py   (materialise the MC >= 12111 branch)
//                     -> scripts/port/maps/apply_map.py (yarn -> mojmap rename)
//                     -> src26/ (compiled)
// Regenerate with scripts/port/port.sh; port26/src is derived and not tracked.
// ---------------------------------------------------------------------------
val portedSrc = layout.projectDirectory.dir("src/main/java")
val portedRes = layout.projectDirectory.dir("src/main/resources")

val preprocess = tasks.register<Exec>("preprocess") {
    description = "Regenerate src26/ from src/ (preprocess + yarn->mojmap rename)"
    workingDir = layout.projectDirectory.asFile
    commandLine("bash", "../scripts/port/port.sh")
    inputs.dir("src")
    inputs.dir("tools")
    // NOT wired into compileJava on purpose: the member-rename loop edits src26/
    // in place between compiles, and an automatic regeneration would silently
    // throw those edits away. Run `gradle preprocess` explicitly when src/ changes.
}

sourceSets["main"].java.setSrcDirs(listOf(portedSrc))
sourceSets["main"].resources.setSrcDirs(listOf(portedRes))

tasks.withType<JavaCompile>().configureEach {
    options.release = targetJava
    options.encoding = "UTF-8"
    // the port starts with thousands of expected name/API errors; javac's default
    // cap of 100 hides the shape of the problem
    options.compilerArgs.addAll(listOf("-Xmaxerrs", "100000", "-Xlint:none"))
}

// Iteration helper: dump the compile classpath so javac can be driven directly
// (scripts/port/diag/DumpDiagnostics.java) instead of going through Gradle every time.
tasks.register("dumpClasspath") {
    val outFile = layout.buildDirectory.file("classpath.txt")
    val cp = sourceSets["main"].compileClasspath
    val src = sourceSets["main"].java.sourceDirectories
    doLast {
        outFile.get().asFile.parentFile.mkdirs()
        outFile.get().asFile.writeText(cp.asPath)
        val srcFile = layout.buildDirectory.file("sources.txt").get().asFile
        srcFile.writeText(
            src.asFileTree.files.joinToString("\n") { it.absolutePath }
        )
        println("classpath entries: ${cp.files.size}")
        println("source files     : ${src.asFileTree.files.size}")
    }
}

tasks.processResources {
    inputs.property("version", project.version.toString())
    filesMatching("fabric.mod.json") {
        expand(mapOf("version" to project.version.toString()))
    }
}
