plugins {
    java
}

group = "io.github.enixes"
version = "0.1.0-SNAPSHOT"

val caffeineVersion = "3.2.4"
val chronicleMapVersion = "2026.1"
val jmhVersion = "1.37"
val junitVersion = "6.1.3"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

val java21Launcher = javaToolchains.launcherFor {
    languageVersion = JavaLanguageVersion.of(21)
}

repositories {
    mavenCentral()
}

val chronicleJvmArgs = listOf(
    "--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED",
    "--add-exports=java.base/jdk.internal.ref=ALL-UNNAMED",
    "--add-exports=java.base/jdk.internal.util=ALL-UNNAMED",
    "--add-exports=java.base/sun.nio.ch=ALL-UNNAMED",
    "--add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
    "--add-exports=jdk.unsupported/sun.misc=ALL-UNNAMED",
    "--add-opens=java.base/java.io=ALL-UNNAMED",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED"
)

dependencies {
    implementation("com.github.ben-manes.caffeine:caffeine:$caffeineVersion")
    implementation("net.openhft:chronicle-map:$chronicleMapVersion")

    testImplementation(platform("org.junit:junit-bom:$junitVersion"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
    jvmArgs(chronicleJvmArgs)
}

val jmh by sourceSets.creating {
    java.srcDir("src/jmh/java")
    resources.srcDir("src/jmh/resources")
    compileClasspath += sourceSets.main.get().output
    runtimeClasspath += sourceSets.main.get().output
}

configurations[jmh.implementationConfigurationName].extendsFrom(configurations.implementation.get())
configurations[jmh.runtimeOnlyConfigurationName].extendsFrom(configurations.runtimeOnly.get())

dependencies {
    add(jmh.implementationConfigurationName, "org.openjdk.jmh:jmh-core:$jmhVersion")
    add(jmh.annotationProcessorConfigurationName, "org.openjdk.jmh:jmh-generator-annprocess:$jmhVersion")
}

fun JavaExec.configureJmhRunner() {
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)

    // Chronicle Map needs these on Java 21. JMH inherits the runner's input
    // arguments into forked benchmark VMs when benchmark-specific JVM args
    // are absent, so this is the single source of the module flags.
    jvmArgs(chronicleJvmArgs)
}

tasks.register<JavaExec>("jmh") {
    group = "benchmark"
    description = "Runs TailCache JMH benchmarks. Pass -PjmhInclude=<regex> to filter."
    configureJmhRunner()

    val include = providers.gradleProperty("jmhInclude").orElse(".*")
    args(include.get())
}

tasks.register<JavaExec>("jmhSmoke") {
    group = "benchmark"
    description = "Runs a deliberately short JMH smoke test; results are not reportable research results."
    configureJmhRunner()
    args(
        ".*CacheSmokeBenchmark.*",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms"
    )
}

tasks.register<JavaExec>("jmhCaffeineAllocSmoke") {
    group = "benchmark"
    description = "Runs a short Caffeine-only JMH allocation smoke check with the built-in GC profiler."
    configureJmhRunner()
    args(
        ".*CacheSmokeBenchmark.*",
        "-p", "backend=CAFFEINE",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-prof", "gc"
    )
}

tasks.register<JavaExec>("jmhCaffeineJfrSmoke") {
    group = "benchmark"
    description = "Runs a short Caffeine-only JMH smoke check with Java Flight Recorder enabled."
    configureJmhRunner()

    val jfrOutputDir = layout.buildDirectory.dir("reports/jmh/jfr").get().asFile.absolutePath
    args(
        ".*CacheSmokeBenchmark.*",
        "-p", "backend=CAFFEINE",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-prof", "jfr:dir=$jfrOutputDir"
    )
}
