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
val hdrHistogramVersion = "2.2.2"

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
    implementation("org.hdrhistogram:HdrHistogram:$hdrHistogramVersion")

    testImplementation(platform("org.junit:junit-bom:$junitVersion"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
    jvmArgs(chronicleJvmArgs)
}

val jmh = sourceSets.create("jmh") {
    java.srcDir("src/jmh/java")
    resources.srcDir("src/jmh/resources")
    compileClasspath += sourceSets.main.get().output
    runtimeClasspath += sourceSets.main.get().output
}

val resultTools = sourceSets.create("resultTools") {
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
        ".*CacheWorkloadBenchmark.mixedWorkload",
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
        ".*CacheWorkloadBenchmark.mixedWorkload",
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
val tailCache06RunId = providers.gradleProperty("tailcacheRunId").orElse("candidate")
val tailCache06RunDir = layout.buildDirectory
    .dir("reports/tailcache06/runs/${tailCache06RunId.get()}")
    .get().asFile

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
        ".*CacheWorkloadBenchmark.mixedWorkload",
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
            // JMH starts internal profilers in declaration order and stops them in reverse.
            // Put the window recorder outside the built-in GC profiler so its sidecar file
            // write is not included in gc.alloc.rate / gc.count / gc.time.
            "-prof", "io.github.enixes.tailcache.benchmark.GcMeasurementWindowProfiler:dir=${gcDir.absolutePath}",
            "-prof", "gc",
            "-prof", "io.github.enixes.tailcache.benchmark.G1GcLogProfiler:dir=${gcDir.absolutePath}"
        )
    }
}

fun registerTailCache06MetadataTask(
    taskName: String,
    resultDir: File,
    runKind: String
) = tasks.register<JavaExec>(taskName) {
    group = "benchmark"
    description = "Writes TailCache 06 raw-result provenance metadata for the $runKind run."
    dependsOn(resultTools.classesTaskName)
    classpath = resultTools.runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.results.TailCacheRunMetadataWriter")
    javaLauncher.set(java21Launcher)

    val javaExecutable = java21Launcher.get().executablePath.asFile.absolutePath
    val runId = if (runKind == "smoke") "smoke" else tailCache06RunId.get()

    args(
        "--out", resultDir.resolve("run-metadata.json").absolutePath,
        "--root", rootDir.absolutePath,
        "--run-kind", runKind,
        "--run-id", runId,
        "--benchmark-java", javaExecutable,
        "--gradle-version", gradle.gradleVersion,
        "--jmh-version", jmhVersion,
        "--caffeine-version", caffeineVersion,
        "--chronicle-version", chronicleMapVersion,
        "--jackson-version", jacksonVersion,
        "--modes", tailCache06Modes.get(),
        "--threads", tailCache06Threads.get()
    )
}

fun registerTailCache06SummaryTask(
    taskName: String,
    resultDir: File,
    latencyTask: TaskProvider<JavaExec>,
    throughputTask: TaskProvider<JavaExec>,
    gcTask: TaskProvider<JavaExec>,
    metadataTask: TaskProvider<JavaExec>
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

// TailCache 07 keeps latency forks unprofiled. Compiler and OS counters belong to
// separate diagnostic forks, with distinct run ids and raw result directories.
fun registerTailCache07JmhTask(
    taskName: String,
    defaultRunId: String,
    diagnostics: Boolean
) = tasks.register<JavaExec>(taskName) {
    group = "benchmark"
    description = if (diagnostics) {
        "Runs TailCache 07 compiler/OS diagnostics separately from latency; not reportable."
    } else {
        "Runs the unprofiled TailCache 07 latency pilot; not reportable until gates pass."
    }
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs + "-Djmh.json.rawData=true")

    val runId = providers.gradleProperty("tailcache07RunId").orElse(defaultRunId)
    val modes = providers.gradleProperty("tailcache07Modes")
        .orElse("CAFFEINE,CHRONICLE_IN_MEMORY,CHRONICLE_PERSISTED")
    val payloads = providers.gradleProperty("tailcache07Payloads").orElse("BYTES_256,KIB_4")
    val threads = providers.gradleProperty("tailcache07Threads").orElse("1")
    val benchmark = providers.gradleProperty("tailcache07Benchmark").orElse("mixedWorkload")
    val warmupIterations = providers.gradleProperty("tailcache07WarmupIterations").orElse("8")
    val forks = providers.gradleProperty("tailcache07Forks").orElse("2")
    val resultDir = layout.buildDirectory.dir("reports/tailcache07/${runId.get()}").get().asFile
    val persistedRoot = layout.buildDirectory.dir("reports/tailcache07/persisted-files").get().asFile
    doFirst {
        if (resultDir.exists() && resultDir.listFiles()?.isNotEmpty() == true) {
            throw GradleException("TailCache 07 run id already has results: ${resultDir.absolutePath}")
        }
        resultDir.mkdirs()
        persistedRoot.mkdirs()
    }

    args(
        ".*CacheWorkloadBenchmark.${benchmark.get()}",
        "-p", "mode=${modes.get()}",
        "-p", "payloadSize=${payloads.get()}",
        "-p", "accessPattern=UNIFORM",
        "-p", "readWriteMix=READ_95_WRITE_5",
        "-t", threads.get(),
        "-wi", warmupIterations.get(), "-i", "5", "-f", forks.get(), "-w", "1s", "-r", "1s",
        "-bm", "sample", "-tu", "ns",
        "-jvmArgsAppend", "-XX:+UseG1GC -Xms512m -Xmx512m "
                + "-Dtailcache.persistedRoot=${persistedRoot.absolutePath}",
        "-rf", "json", "-rff", resultDir.resolve("results.json").absolutePath,
        "-o", resultDir.resolve("jmh.txt").absolutePath,
        "-foe", "true"
    )
    if (diagnostics) {
        args(
            "-prof", "io.github.enixes.tailcache.benchmark.PilotOsCountersProfiler:dir=${resultDir.absolutePath}",
            "-prof", "comp"
        )
    }
}
registerTailCache07JmhTask("tailCache07Pilot", "pilot", diagnostics = false)
registerTailCache07JmhTask("tailCache07PilotDiagnostics", "pilot-diagnostics", diagnostics = true)

// TailCache 08 runs one payload/order block at a time. The coordinator writes
// machine provenance and combines blocks only after their raw files are safe.
fun registerTailCache08JmhTask(taskName: String, kind: String) = tasks.register<JavaExec>(taskName) {
    group = "benchmark"
    description = "Runs a TailCache 08 $kind block; use scripts/tailcache08.py for the matrix."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("org.openjdk.jmh.Main")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs + "-Djmh.json.rawData=true")

    val runId = providers.gradleProperty("tailcache08RunId").orElse("candidate")
    val block = providers.gradleProperty("tailcache08Block").orElse("block")
    val modes = providers.gradleProperty("tailcache08Modes")
        .orElse("CAFFEINE,CHRONICLE_IN_MEMORY,CHRONICLE_PERSISTED")
    val payload = providers.gradleProperty("tailcache08Payload").orElse("BYTES_256")
    val warmup = providers.gradleProperty("tailcache08WarmupIterations").orElse("12")
    val measurement = providers.gradleProperty("tailcache08MeasurementIterations").orElse("8")
    val forks = providers.gradleProperty("tailcache08Forks").orElse("3")
    val resultDir = layout.buildDirectory
        .dir("reports/tailcache08/${runId.get()}/${block.get()}/$kind").get().asFile
    val persistedRoot = layout.buildDirectory.dir("reports/tailcache08/persisted-files").get().asFile
    doFirst {
        if (!runId.get().matches(Regex("[A-Za-z0-9._-]+"))
                || !block.get().matches(Regex("[A-Za-z0-9._-]+"))) {
            throw GradleException("TailCache 08 run id and block must use letters, digits, dot, underscore, or dash")
        }
        if (resultDir.exists() && resultDir.listFiles()?.isNotEmpty() == true) {
            throw GradleException("TailCache 08 raw block already exists: ${resultDir.absolutePath}")
        }
        resultDir.mkdirs()
        persistedRoot.mkdirs()
        if (kind == "jfr") resultDir.resolve("recordings").mkdirs()
    }
    args(
        ".*CacheWorkloadBenchmark.mixedWorkload",
        "-p", "mode=${modes.get()}",
        "-p", "payloadSize=${payload.get()}",
        "-p", "accessPattern=UNIFORM",
        "-p", "readWriteMix=READ_95_WRITE_5",
        "-t", "1",
        "-wi", warmup.get(), "-i", measurement.get(), "-f", forks.get(),
        "-w", "1s", "-r", "1s",
        "-bm", if (kind == "throughput") "thrpt" else "sample",
        "-tu", if (kind == "throughput") "s" else "ns",
        "-jvmArgsAppend", "-XX:+UseG1GC -Xms512m -Xmx512m "
                + "-Dtailcache.persistedRoot=${persistedRoot.absolutePath}",
        "-rf", "json", "-rff", resultDir.resolve("results.json").absolutePath,
        "-o", resultDir.resolve("jmh.txt").absolutePath,
        "-foe", "true"
    )
    if (kind == "diagnostics") {
        args(
            "-prof", "io.github.enixes.tailcache.benchmark.PilotOsCountersProfiler:dir=${resultDir.absolutePath}",
            "-prof", "comp"
        )
    }
    if (kind == "jfr") {
        args("-prof", "jfr:dir=${resultDir.resolve("recordings").absolutePath}")
    }
}
registerTailCache08JmhTask("tailCache08Latency", "latency")
registerTailCache08JmhTask("tailCache08Throughput", "throughput")
registerTailCache08JmhTask("tailCache08Diagnostics", "diagnostics")
registerTailCache08JmhTask("tailCache08Jfr", "jfr")

fun registerTailCache09JmhTask(taskName: String, mode: String, unit: String) =
    tasks.register<JavaExec>(taskName) {
        group = "benchmark"
        description = "Runs TailCache 09 Chronicle sizing $mode; capacity probe is separate."
        dependsOn(jmh.classesTaskName)
        classpath = jmh.runtimeClasspath
        mainClass.set("org.openjdk.jmh.Main")
        javaLauncher.set(java21Launcher)
        jvmArgs(chronicleJvmArgs + "-Djmh.json.rawData=true")
        val runId = providers.gradleProperty("tailcache09RunId").orElse("candidate")
        val warmup = providers.gradleProperty("tailcache09WarmupIterations").orElse("8")
        val measurement = providers.gradleProperty("tailcache09MeasurementIterations").orElse("5")
        val forks = providers.gradleProperty("tailcache09Forks").orElse("2")
        val estimates = providers.gradleProperty("tailcache09Estimates")
            .orElse("HALF,MATCH,DOUBLE,CONSTANT")
        val payloads = providers.gradleProperty("tailcache09Payloads").orElse("256,4096")
        val resultDir = layout.buildDirectory.dir("reports/tailcache09/${runId.get()}/$mode").get().asFile
        doFirst {
            if (!runId.get().matches(Regex("[A-Za-z0-9._-]+"))) {
                throw GradleException("TailCache 09 run id has invalid characters")
            }
            if (resultDir.exists() && resultDir.listFiles()?.isNotEmpty() == true) {
                throw GradleException("TailCache 09 raw result already exists: ${resultDir.absolutePath}")
            }
            resultDir.mkdirs()
        }
        args(
            ".*ChronicleSizingBenchmark.mixedWorkload",
            "-p", "estimate=${estimates.get()}",
            "-p", "actualPayloadBytes=${payloads.get()}",
            "-t", "1", "-wi", warmup.get(), "-i", measurement.get(),
            "-f", forks.get(), "-w", "1s", "-r", "1s",
            "-bm", mode, "-tu", unit,
            "-jvmArgsAppend", "-XX:+UseG1GC -Xms512m -Xmx512m",
            "-rf", "json", "-rff", resultDir.resolve("results.json").absolutePath,
            "-o", resultDir.resolve("jmh.txt").absolutePath,
            "-foe", "true"
        )
    }
registerTailCache09JmhTask("tailCache09Latency", "sample", "ns")
registerTailCache09JmhTask("tailCache09Throughput", "thrpt", "s")

tasks.register<JavaExec>("tailCache09Capacity") {
    group = "benchmark"
    description = "Probes Chronicle sizing capacity and first failure outside timed JMH runs."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.benchmark.ChronicleSizingCapacityProbe")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs + listOf("-Xms512m", "-Xmx512m"))
    val runId = providers.gradleProperty("tailcache09RunId").orElse("candidate")
    val resultDir = layout.buildDirectory.dir("reports/tailcache09/${runId.get()}/capacity").get().asFile
    doFirst {
        if (!runId.get().matches(Regex("[A-Za-z0-9._-]+"))) {
            throw GradleException("TailCache 09 run id has invalid characters")
        }
        if (resultDir.exists() && resultDir.listFiles()?.isNotEmpty() == true) {
            throw GradleException("TailCache 09 capacity result already exists: ${resultDir.absolutePath}")
        }
        resultDir.mkdirs()
    }
    args(resultDir.resolve("capacity.csv").absolutePath, resultDir.resolve("scratch").absolutePath)
}

tasks.register<JavaExec>("tailCache07OpenDiagnostic") {
    group = "benchmark"
    description = "Runs separate persisted reopen/first-touch diagnostics (OS cache is not dropped)."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.benchmark.PersistedOpenDiagnostic")
    javaLauncher.set(java21Launcher)
    jvmArgs(chronicleJvmArgs + listOf("-Xms512m", "-Xmx512m"))
    val diagnosticDir = layout.buildDirectory.dir("reports/tailcache07/open-diagnostic").get().asFile
    val persistedRoot = layout.buildDirectory.dir("reports/tailcache07/persisted-files").get().asFile
    args(persistedRoot.absolutePath, diagnosticDir.resolve("open-diagnostic.csv").absolutePath)
}

// Task 12 parameters are exploratory until pressure calibration and the pilot freeze them.
val tailCache12RunId = providers.gradleProperty("tailcache12RunId").orElse("development")
val tailCache12Heap = providers.gradleProperty("tailcache12HeapMiB").orElse("512")
val tailCache12Backends = providers.gradleProperty("tailcache12Backends").orElse("CAFFEINE,CHRONICLE_IN_MEMORY")
val tailCache12Payloads = providers.gradleProperty("tailcache12Payloads").orElse("256,4096")
val tailCache12Residents = providers.gradleProperty("tailcache12Residents").orElse("8192")
val tailCache12LiveBytes = providers.gradleProperty("tailcache12LiveBytes").orElse("0")
val tailCache12Churn = providers.gradleProperty("tailcache12ChurnBytesPerSecond").orElse("16777216")
val tailCache12Seed = providers.gradleProperty("tailcache12Seed").orElse("24301")

fun tailCache12Directory(kind: String): File {
    require(tailCache12RunId.get().matches(Regex("[A-Za-z0-9._-]+"))) { "Invalid Task 12 run id" }
    require(tailCache12Heap.get().toInt() >= 64) { "Task 12 heap must be at least 64 MiB" }
    return layout.buildDirectory.dir("reports/tailcache12/${tailCache12RunId.get()}/$kind").get().asFile
}

fun registerTailCache12Jmh(taskName: String, kind: String, smoke: Boolean = false) =
    tasks.register<JavaExec>(taskName) {
        group = "benchmark"
        description = "Task 12 crossover $kind channel; calibration/pilot gates still required."
        dependsOn(jmh.classesTaskName)
        classpath = jmh.runtimeClasspath
        mainClass.set("org.openjdk.jmh.Main")
        javaLauncher.set(java21Launcher)
        jvmArgs(chronicleJvmArgs + "-Djmh.json.rawData=true")
        val directory = tailCache12Directory(kind)
        doFirst {
            if (directory.exists() && directory.listFiles()?.isNotEmpty() == true) {
                throw GradleException("Refusing existing Task 12 results: ${directory.absolutePath}")
            }
            directory.mkdirs()
        }
        val warmups = providers.gradleProperty("tailcache12Warmups").orElse(if (smoke) "1" else "12")
        val measurements = providers.gradleProperty("tailcache12Measurements").orElse(if (smoke) "1" else "8")
        val forks = providers.gradleProperty("tailcache12Forks").orElse(if (smoke) "1" else "3")
        val duration = if (smoke) "300ms" else "1s"
        val jvmOptions = mutableListOf("-XX:+UseG1GC", "-Xms${tailCache12Heap.get()}m", "-Xmx${tailCache12Heap.get()}m")
        jvmOptions.add("-Dtailcache12.observationDir=${directory.absolutePath}")
        if (kind == "compiler" || kind == "allocation") {
            jvmOptions.add("-Xlog:gc*,safepoint:file=${directory.resolve("gc-%p.log").absolutePath}:uptimemillis,timenanos,level,tags:filecount=0")
        }
        if (kind == "compiler") {
            jvmOptions.addAll(listOf("-Dtailcache12.compilerWindow=true", "-XX:+UnlockDiagnosticVMOptions", "-XX:+LogCompilation",
                "-XX:LogFile=${directory.resolve("jit-%p.xml").absolutePath}"))
        }
        args(
            ".*CrossoverBenchmark." + if (kind == "floor") "freshSupplyFloor" else "mixedWorkload",
            "-p", "backend=${tailCache12Backends.get()}", "-p", "payloadBytes=${tailCache12Payloads.get()}",
            "-p", "residentEntries=${tailCache12Residents.get()}",
            "-p", "applicationLiveBytes=${tailCache12LiveBytes.get()}",
            "-p", "churnBytesPerSecond=${tailCache12Churn.get()}", "-p", "seed=${tailCache12Seed.get()}",
            "-t", "1", "-wi", warmups.get(), "-i", measurements.get(), "-f", forks.get(),
            "-w", duration, "-r", duration,
            "-bm", if (kind in listOf("throughput", "allocation")) "thrpt" else "sample",
            "-tu", if (kind in listOf("throughput", "allocation")) "s" else "ns",
            "-jvmArgsAppend", jvmOptions.joinToString(" "),
            "-rf", "json", "-rff", directory.resolve("results.json").absolutePath,
            "-o", directory.resolve("jmh.txt").absolutePath, "-foe", "true"
        )
        if (kind == "compiler") args("-prof", "comp")
        if (kind == "allocation") args("-prof", "gc")
    }

registerTailCache12Jmh("tailCache12Smoke", "smoke", smoke = true)
registerTailCache12Jmh("tailCache12Sample", "sample")
registerTailCache12Jmh("tailCache12Throughput", "throughput")
registerTailCache12Jmh("tailCache12Compiler", "compiler")
registerTailCache12Jmh("tailCache12Allocation", "allocation")
registerTailCache12Jmh("tailCache12SupplyFloor", "floor")

tasks.register<JavaExec>("tailCache12EveryOperation") {
    group = "benchmark"
    description = "Task 12 every-operation/gap channel with explicit validation-only pause injection."
    dependsOn(sourceSets.main.get().classesTaskName)
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.workload.CrossoverLatencyRunner")
    javaLauncher.set(java21Launcher)
    val directory = tailCache12Directory("every-operation")
    doFirst {
        if (directory.exists() && directory.listFiles()?.isNotEmpty() == true) {
            throw GradleException("Refusing existing Task 12 results: ${directory.absolutePath}")
        }
        directory.mkdirs()
    }
    val compilerDiagnostics = providers.gradleProperty("tailcache12CompilerDiagnostics").orElse("false").get().toBoolean()
    jvmArgs(chronicleJvmArgs + listOf("-XX:+UseG1GC", "-Xms${tailCache12Heap.get()}m", "-Xmx${tailCache12Heap.get()}m",
        "-Xlog:gc*,safepoint:file=${directory.resolve("gc-%p.log").absolutePath}:uptimemillis,timenanos,level,tags:filecount=0"))
    if (compilerDiagnostics) jvmArgs("-XX:+UnlockDiagnosticVMOptions", "-XX:+LogCompilation",
        "-XX:LogFile=${directory.resolve("jit-%p.xml").absolutePath}")
    args("--out", directory.resolve("worker").absolutePath,
        "--backend", providers.gradleProperty("tailcache12Backend").orElse("CAFFEINE").get(),
        "--payload", providers.gradleProperty("tailcache12Payload").orElse("256").get(),
        "--residents", tailCache12Residents.get(), "--application-live-bytes", tailCache12LiveBytes.get(),
        "--churn-bytes-sec", tailCache12Churn.get(), "--seed", tailCache12Seed.get(),
        "--warmup", providers.gradleProperty("tailcache12Warmups").orElse("12").get(),
        "--measure", providers.gradleProperty("tailcache12Measurements").orElse("8").get(),
        "--iteration-ms", providers.gradleProperty("tailcache12IterationMs").orElse("1000").get(),
        "--validation", providers.gradleProperty("tailcache12Validation").orElse("none").get(),
        "--timer-floor", providers.gradleProperty("tailcache12TimerFloor").orElse("false").get(),
        "--compiler-diagnostics", compilerDiagnostics.toString())
}

tasks.register<JavaExec>("tailCache12Retention") {
    group = "benchmark"
    description = "Task 12 full-GC retained-object diagnostic; not a campaign measurement."
    dependsOn(jmh.classesTaskName)
    classpath = jmh.runtimeClasspath
    mainClass.set("io.github.enixes.tailcache.benchmark.CrossoverRetentionDiagnostic")
    javaLauncher.set(java21Launcher)
    val backend = providers.gradleProperty("tailcache12Backend").orElse("CAFFEINE").get()
    val payload = providers.gradleProperty("tailcache12Payload").orElse("4096").get()
    val directory = tailCache12Directory("retention-$backend-${tailCache12Residents.get()}-$payload")
    jvmArgs(chronicleJvmArgs + listOf("-XX:+UseG1GC", "-Xms${tailCache12Heap.get()}m", "-Xmx${tailCache12Heap.get()}m"))
    args(backend, tailCache12Residents.get(), payload, directory.absolutePath)
}
