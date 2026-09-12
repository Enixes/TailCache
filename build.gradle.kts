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
    "--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED",
    "-Dchronicle.analytics.disable=true"
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

tasks.register<JavaExec>("jmh") {
    group = "benchmark"
    description = "Runs TailCache JMH benchmarks. Pass -PjmhInclude=<regex> to filter."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)

    val include = providers.gradleProperty("jmhInclude").orElse(".*")
    args(include.get())
}

tasks.register<JavaExec>("jmhSmoke") {
    group = "benchmark"
    description = "Runs a deliberately short JMH smoke test; results are not reportable research results."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)
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
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)
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
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)

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

tasks.register<JavaExec>("jmhChronicleAllocSmoke") {
    group = "benchmark"
    description = "Runs a short Chronicle Map-only JMH allocation smoke check with the built-in GC profiler."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)
    args(
        ".*CacheSmokeBenchmark.*",
        "-p", "backend=CHRONICLE_MAP",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-prof", "gc"
    )
}

tasks.register<JavaExec>("jmhChronicleJfrSmoke") {
    group = "benchmark"
    description = "Runs a short Chronicle Map-only JMH smoke check with Java Flight Recorder enabled."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)

    val jfrOutputDir = layout.buildDirectory.dir("reports/jmh/jfr").get().asFile.absolutePath
    args(
        ".*CacheSmokeBenchmark.*",
        "-p", "backend=CHRONICLE_MAP",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-prof", "jfr:dir=$jfrOutputDir"
    )
}

tasks.register<JavaExec>("jmhWorkloadSmoke") {
    group = "benchmark"
    description = "Runs the TailCache 05 mixed-workload matrix with one shared-cache worker; diagnostic only."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)

    val resultDir = layout.buildDirectory.dir("reports/jmh").get().asFile
    val resultFile = resultDir.resolve("workload-smoke-1t.json")
    doFirst { resultDir.mkdirs() }
    args(
        ".*CacheWorkloadBenchmark.*",
        "-t", "1",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-rf", "json",
        "-rff", resultFile.absolutePath
    )
}

tasks.register<JavaExec>("jmhWorkloadShared16Smoke") {
    group = "benchmark"
    description = "Runs the TailCache 05 matrix with 16 workers sharing one cache instance; diagnostic only."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs)

    val resultDir = layout.buildDirectory.dir("reports/jmh").get().asFile
    val resultFile = resultDir.resolve("workload-smoke-16t.json")
    doFirst { resultDir.mkdirs() }
    args(
        ".*CacheWorkloadBenchmark.*",
        "-t", "16",
        "-wi", "1",
        "-i", "1",
        "-f", "1",
        "-w", "300ms",
        "-r", "300ms",
        "-rf", "json",
        "-rff", resultFile.absolutePath
    )
}
