plugins {
    java
}

group = "io.github.enixes"
version = "0.1.0-SNAPSHOT"

val caffeineVersion = "3.2.4"
val chronicleMapVersion = "2026.1"
val jmhVersion = "1.37"
val junitVersion = "6.1.3"
val jacksonVersion = "2.22.2"

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

val resultTools by sourceSets.creating {
    java.srcDir("src/results/java")
}

configurations[jmh.implementationConfigurationName].extendsFrom(configurations.implementation.get())
configurations[jmh.runtimeOnlyConfigurationName].extendsFrom(configurations.runtimeOnly.get())

dependencies {
    add(jmh.implementationConfigurationName, "org.openjdk.jmh:jmh-core:$jmhVersion")
    add(jmh.annotationProcessorConfigurationName, "org.openjdk.jmh:jmh-generator-annprocess:$jmhVersion")
    add(resultTools.implementationConfigurationName, "com.fasterxml.jackson.core:jackson-databind:$jacksonVersion")
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


val tailCache06Modes = providers.gradleProperty("tailcacheModes")
    .orElse("CAFFEINE,CHRONICLE_IN_MEMORY")
val tailCache06Threads = providers.gradleProperty("tailcacheThreads").orElse("1")

val tailCache06SmokeDir = layout.buildDirectory.dir("reports/tailcache06/smoke").get().asFile
val tailCache06RunDir = layout.buildDirectory.dir("reports/tailcache06/run").get().asFile

fun registerTailCache06JmhTask(
    taskName: String,
    descriptionText: String,
    resultDir: File,
    stem: String,
    benchmarkMode: String,
    timeUnit: String,
    profiled: Boolean,
    smoke: Boolean
) = tasks.register<JavaExec>(taskName) {
    group = "benchmark"
    description = descriptionText
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs + "-Djmh.json.rawData=true")

    val resultFile = resultDir.resolve("$stem.json")
    val textFile = resultDir.resolve("$stem.txt")
    val gcDir = resultDir.resolve("gc")

    doFirst {
        resultDir.mkdirs()
        resultFile.delete()
        textFile.delete()
        if (profiled) {
            gcDir.deleteRecursively()
            gcDir.mkdirs()
        }
    }

    args(
        ".*CacheWorkloadBenchmark.*",
        "-p", "mode=${tailCache06Modes.get()}",
        "-t", tailCache06Threads.get(),
        "-bm", benchmarkMode,
        "-tu", timeUnit,
        "-jvmArgsAppend", "-XX:+UseG1GC",
        "-rf", "json",
        "-rff", resultFile.absolutePath,
        "-o", textFile.absolutePath,
        "-foe", "true"
    )

    if (smoke) {
        args(
            "-wi", "1",
            "-i", "1",
            "-f", "1",
            "-w", "300ms",
            "-r", "300ms"
        )
    }

    if (profiled) {
        args(
            "-prof", "gc",
            "-prof", "io.github.enixes.tailcache.benchmark.GcPauseProfiler:dir=${gcDir.absolutePath}"
        )
    }
}

fun commandOutput(vararg command: String): String {
    return try {
        val process = ProcessBuilder(*command)
            .directory(rootDir)
            .redirectErrorStream(true)
            .start()
        val output = process.inputStream.bufferedReader().use { it.readText() }.trim()
        val exit = process.waitFor()
        if (exit == 0) output else "<command failed: ${command.joinToString(" ")}>"
    } catch (exception: Exception) {
        "<unavailable: ${exception.javaClass.simpleName}>"
    }
}

fun registerTailCache06MetadataTask(taskName: String, resultDir: File, runKind: String) =
    tasks.register(taskName) {
        group = "benchmark"
        description = "Writes TailCache 06 raw-result provenance metadata for the $runKind run."
        doLast {
            resultDir.mkdirs()
            val javaExecutable = java21Launcher.get().executablePath.asFile.absolutePath
            val gitStatus = commandOutput("git", "status", "--porcelain")
            val metadata = linkedMapOf<String, Any>(
                "schemaVersion" to "tailcache-run-metadata-v1",
                "generatedAtUtc" to java.time.Instant.now().toString(),
                "runKind" to runKind,
                "gitCommit" to commandOutput("git", "rev-parse", "HEAD"),
                "gitDirty" to gitStatus.isNotBlank(),
                "gitStatusPorcelain" to gitStatus,
                "benchmarkJavaExecutable" to javaExecutable,
                "benchmarkJavaVersion" to commandOutput(javaExecutable, "-version"),
                "gradleVersion" to gradle.gradleVersion,
                "jmhVersion" to jmhVersion,
                "caffeineVersion" to caffeineVersion,
                "chronicleMapVersion" to chronicleMapVersion,
                "jacksonResultToolVersion" to jacksonVersion,
                "modes" to tailCache06Modes.get(),
                "threads" to tailCache06Threads.get(),
                "collector" to "G1",
                "metricSources" to linkedMapOf(
                    "latency" to "unprofiled JMH SampleTime",
                    "throughput" to "unprofiled JMH Throughput",
                    "allocationAndCollection" to "JMH gc profiler via MXBeans",
                    "gcPauses" to "TailCache GcPauseProfiler parsing measurement-window -Xlog:gc=info Pause records"
                ),
                "rawFiles" to listOf(
                    "latency.json", "latency.txt",
                    "throughput.json", "throughput.txt",
                    "gc-profile.json", "gc-profile.txt",
                    "gc/*.log"
                )
            )
            val json = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(metadata))
            resultDir.resolve("run-metadata.json").writeText(json + "\n")
        }
    }

fun registerTailCache06SummaryTask(
    taskName: String,
    resultDir: File,
    latencyTask: TaskProvider<JavaExec>,
    throughputTask: TaskProvider<JavaExec>,
    gcTask: TaskProvider<JavaExec>,
    metadataTask: TaskProvider<Task>
) = tasks.register<JavaExec>(taskName) {
    group = "benchmark"
    description = "Joins TailCache 06 latency, throughput, allocation and GC results."
    dependsOn(resultTools.classesTaskName, latencyTask, throughputTask, gcTask, metadataTask)
    classpath = resultTools.runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.results.TailCacheResultSummarizer")
    javaLauncher.set(java21Launcher)

    args(
        "--latency", resultDir.resolve("latency.json").absolutePath,
        "--throughput", resultDir.resolve("throughput.json").absolutePath,
        "--gc", resultDir.resolve("gc-profile.json").absolutePath,
        "--metadata", resultDir.resolve("run-metadata.json").absolutePath,
        "--out-json", resultDir.resolve("summary.json").absolutePath,
        "--out-csv", resultDir.resolve("summary.csv").absolutePath
    )
}

val tailCache06SmokeLatency = registerTailCache06JmhTask(
    "jmhTailCache06SmokeLatency",
    "TailCache 06 smoke: unprofiled SampleTime latency distribution.",
    tailCache06SmokeDir,
    "latency",
    "sample",
    "ns",
    profiled = false,
    smoke = true
)
val tailCache06SmokeThroughput = registerTailCache06JmhTask(
    "jmhTailCache06SmokeThroughput",
    "TailCache 06 smoke: unprofiled throughput.",
    tailCache06SmokeDir,
    "throughput",
    "thrpt",
    "s",
    profiled = false,
    smoke = true
)
val tailCache06SmokeGc = registerTailCache06JmhTask(
    "jmhTailCache06SmokeGc",
    "TailCache 06 smoke: allocation, collection and G1 pause metrics.",
    tailCache06SmokeDir,
    "gc-profile",
    "thrpt",
    "s",
    profiled = true,
    smoke = true
)
tailCache06SmokeThroughput.configure { mustRunAfter(tailCache06SmokeLatency) }
tailCache06SmokeGc.configure { mustRunAfter(tailCache06SmokeThroughput) }
val tailCache06SmokeMetadata = registerTailCache06MetadataTask(
    "tailCache06SmokeMetadata",
    tailCache06SmokeDir,
    "smoke"
)
val tailCache06SmokeSummary = registerTailCache06SummaryTask(
    "tailCache06SmokeSummary",
    tailCache06SmokeDir,
    tailCache06SmokeLatency,
    tailCache06SmokeThroughput,
    tailCache06SmokeGc,
    tailCache06SmokeMetadata
)
tasks.register("tailCache06Smoke") {
    group = "benchmark"
    description = "Runs and summarizes the short TailCache 06 result-pipeline validation."
    dependsOn(tailCache06SmokeSummary)
}

val tailCache06Latency = registerTailCache06JmhTask(
    "jmhTailCache06Latency",
    "TailCache 06 candidate run: unprofiled SampleTime latency distribution.",
    tailCache06RunDir,
    "latency",
    "sample",
    "ns",
    profiled = false,
    smoke = false
)
val tailCache06Throughput = registerTailCache06JmhTask(
    "jmhTailCache06Throughput",
    "TailCache 06 candidate run: unprofiled throughput.",
    tailCache06RunDir,
    "throughput",
    "thrpt",
    "s",
    profiled = false,
    smoke = false
)
val tailCache06Gc = registerTailCache06JmhTask(
    "jmhTailCache06Gc",
    "TailCache 06 candidate run: allocation, collection and G1 pause metrics.",
    tailCache06RunDir,
    "gc-profile",
    "thrpt",
    "s",
    profiled = true,
    smoke = false
)
tailCache06Throughput.configure { mustRunAfter(tailCache06Latency) }
tailCache06Gc.configure { mustRunAfter(tailCache06Throughput) }
val tailCache06Metadata = registerTailCache06MetadataTask(
    "tailCache06Metadata",
    tailCache06RunDir,
    "candidate"
)
val tailCache06Summary = registerTailCache06SummaryTask(
    "tailCache06Summary",
    tailCache06RunDir,
    tailCache06Latency,
    tailCache06Throughput,
    tailCache06Gc,
    tailCache06Metadata
)
tasks.register("tailCache06") {
    group = "benchmark"
    description = "Runs and summarizes the TailCache 06 result pipeline using benchmark defaults."
    dependsOn(tailCache06Summary)
}
