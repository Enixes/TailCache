# Targeted result-transport preparation plan — 5 November 2026

This plan precedes implementation and new collection. Source f5463b4be929d80f101640ea7eef1a0908d4c2305e28a6c462bd972cc3690731 failed qualification. Its Caffeine256 fork had a15-ms seventh analysis interval despite passing host checks. The next Caffeine4096 fork recorded20 ms in the same ordinal and independently failed the CPU screen. Both remain rejected; later screen/recorder/floor stages were not launched. No previous raw measurement is relabeled or pooled.

## Concrete attribution

XML in both failing forks shows ObjectOutputStream.BlockDataOutputStream.writeBytes and getUTFLength plus Arrays.fill compiling across those analysis intervals. The clean256 fork's task wall durations were approximately7/4/3 ms, and its real worker/compiler counters recorded15 ms. The4096 fork showed approximately7/5/5 ms and a20-ms counter; host disturbance limits that fork's performance interpretation. No worker-window uncommon traps were found. Task wall duration is not compiler CPU time or worker pause duration.

JMH1.37 BinaryLinkClient uses ObjectOutputStream over a64-KiB BufferedOutputStream over a Socket, periodically resetting the serialization reference table. The pinned source explicitly resets every100 frames by default. Its warmup does not transmit structured IterationResult frames, so ordinary120-second warmup does not exercise all these paths; eight fixed measurement-mode conditioning iterations also proved insufficient. Reference: https://github.com/openjdk/jmh/blob/1.37/jmh-core/src/main/java/org/openjdk/jmh/runner/link/BinaryLinkClient.java#L49-L114 .

## Repair, without another duration escalation

Before measured cache construction in each JMH fork, serialize256 representative pinned-JMH result object graphs through an isolated loopback socket with a64-KiB buffered ObjectOutputStream. Reset before each scratch frame to exercise descriptor/UTF/reference-table paths repeatedly. Use SampleTime/throughput/scalar result classes and actual immutable benchmark metadata, with a1024-bin scratch sample buffer. All data go only to a private local discard receiver, never to JMH's actual binary result connection or the observation/result files. No synthetic operation or histogram enters any retained conditioning/analysis dataset.

Join and close the discard receiver and both sockets before measured-state construction; use bounded connect/read/join times and fail startup on any error. Retain only primitive byte/frame/checksum evidence after preparation, no scratch result, array, cache or socket reference. Record a fixed transport-preparation version,256-frame count and received-byte count in setup metadata. Both backends and all JMH channels receive the same preparation. The every-operation recorder has no per-iteration JMH result transport and does not run this helper; its channel-specific state remains independently calibrated.

Activate this only under an explicit protocol control jmh-result-transport-v1; normal warmup120,conditioning8,analysis8 and every numeric acceptance gate stay fixed. This is a targeted setup repair supported by identified serialization tasks, not permission to increase durations until a pass. Priming necessarily changes shared JVM profiles; fresh source-matched qualification and observer floors are mandatory, and any later compiler violation still rejects the analysis fork.

## Verification and next sequence

Test the generic isolated transport's reset/write count, receiver byte delivery, worker shutdown and invalid-bound rejection. Compile the actual JMH fixture graph against pinned1.37. Verify raw primary iteration/histogram counts remain16 physical/eight analysis and require explicit metadata/version/positive preparation bytes in new-protocol parsers. Preserve legacy replay without retrofitting this preparation control. Review implementation before collection.

Then declare native-final-transport-20261105-001: controlled CPU probe, quiet preparation, functional/pause validation, complete120/8/8 JMH and actual-recorder compiler screens, two pressure96 diagnostics and new independent floors. Stop at any failure. No calibration may be launched until this entire source-matched sequence and its review pass. All rejected evidence remains retained.
