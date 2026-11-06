import csv
import json
import pathlib
import tempfile
import unittest

import tailcache12 as evidence
import tailcache12_calibrate as calibration
from tailcache12_study_analysis import jmh_fork_summary


class ConditioningTest(unittest.TestCase):
    def test_high_first_calibration_is_explicit_and_keeps_reversed_replica_controls(self):
        inputs=dict(liveBytes=[0,96,208,288],payloads=[4096,256],residents=32768,heapMiB=512,
            churnBytesPerSecond=32*1024**2,seed=24301,warmups=120,conditioning=8,
            transportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,measurements=8,repeats=2,
            channels=list(calibration.CHANNELS),highFirst=True)
        plan=calibration.calibration_grid(inputs)
        self.assertEqual(64,len(plan))
        self.assertEqual(288,plan[0][1]["LiveBytes"])
        self.assertEqual(4096,plan[0][1]["Payload"])
        self.assertEqual([p for _,p in plan[:32]],[p for _,p in reversed(plan[32:])])
        self.assertTrue(all(p["Conditioning"]==8 and p["TransportWarmupVersion"]==evidence.TRANSPORT_WARMUP_VERSION for _,p in plan))
        inputs.pop("highFirst")
        self.assertEqual(0,calibration.calibration_grid(inputs)[0][1]["LiveBytes"])

    def test_only_predeclared_analysis_histograms_supply_endpoints_and_all_phases_validate(self):
        for conditioning in (8,16):
            with self.subTest(conditioning=conditioning): self.assert_conditioning(conditioning)

    def assert_conditioning(self,conditioning):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            sample=root/"sample"
            sample.mkdir()
            inputs=dict(Backend="CAFFEINE",Payload=256,Residents=8192,LiveBytes=0,ChurnBytesPerSecond=1024,
                        Seed=24301,Warmups=12,Conditioning=conditioning,Measurements=8,HeapMiB=512)
            runtime=dict(jmhVersion="1.37",jdkVersion="21",vmName="VM",vmVersion="build")
            record=dict(runtime,benchmark="io.github.enixes.tailcache.benchmark.CrossoverBenchmark.mixedWorkload",
                forks=1,threads=1,mode="sample",warmupIterations=12,measurementIterations=conditioning+8,warmupTime="1 s",measurementTime="1 s",
                jvmArgs=["-Xms512m","-Xmx512m","-XX:+UseG1GC",f"-Dtailcache12.conditioningIterations={conditioning}"],
                params=dict(backend="CAFFEINE",payloadBytes="256",residentEntries="8192",applicationLiveBytes="0",
                            churnBytesPerSecond="1024",seed="24301"),secondaryMetrics={},
                primaryMetric=dict(scoreUnit="ns/op",rawDataHistogram=[[[[10240,12500]]]*conditioning+[[[100,12500]]]*8],scorePercentiles={"99.9":10240}))
            trace="a"*64
            (sample/"jmh.txt").write_text(f"traceSha256={trace} valueGenerator=xorshift-key-version-v1 conditioningIterations={conditioning}\n[TailCache12][integrity]\n")
            rows=[]
            for phase,count in (("WARMUP",12),("CONDITIONING",conditioning),("MEASUREMENT",8)):
                for _ in range(count):
                    i=len(rows)+1
                    rows.append(dict(phase=phase,envelopeStartNs=i*10**9,envelopeEndNs=(i+1)*10**9,operations=100000,
                        workerEnvelopeCompilerMs=99 if phase=="CONDITIONING" else 0,
                        churnPayloadBytesPerSecond=1024,churnDroppedBytes=0,churnJvmAllocatedBytes=1024,churnPayloadBytes=1024))
            def write():
                (sample/"results.json").write_text(json.dumps([record]))
                with (sample/"iterations-1.csv").open("w",newline="") as stream:
                    writer=csv.DictWriter(stream,list(rows[0]));writer.writeheader();writer.writerows(rows)
            def analyze(): return jmh_fork_summary(root,"sample",inputs,trace,runtime)
            write(); result=analyze()
            self.assertTrue(result["accepted"])
            self.assertEqual(100,result["servicePercentilesNs"]["99.9"])
            self.assertEqual(100000,result["sampleCount"])
            self.assertEqual([0]*8,result["compilerPerIterationMs"])
            self.assertTrue(result["reportedJmhPercentilesIncludeConditioning"])
            with self.assertRaises(ValueError): jmh_fork_summary(root,"sample",dict(inputs,Conditioning=0),trace,runtime)
            record["measurementIterations"]=8;write()
            with self.assertRaises(ValueError): analyze()
            record["measurementIterations"]=conditioning+8
            rows[12]["operations"]=100;write()
            with self.assertRaises(ValueError): analyze()
            rows[12]["operations"]=100000
            rows[12]["phase"],rows[12+conditioning]["phase"]=rows[12+conditioning]["phase"],rows[12]["phase"];write()
            with self.assertRaises(ValueError): analyze()
            rows[12]["phase"],rows[12+conditioning]["phase"]=rows[12+conditioning]["phase"],rows[12]["phase"]
            rows[12+conditioning]["workerEnvelopeCompilerMs"]=11;write()
            self.assertFalse(analyze()["accepted"])

    def test_broad_compiler_gate_uses_fixed_analysis_count_and_preserves_legacy_count(self):
        record=dict(secondaryMetrics={"compiler.time.profiled":dict(score=800,rawData=[[99]*8+[1]*8])})
        total,values=evidence.compiler_profile_values(record,8)
        self.assertEqual((8,[1]*8),(total,values))
        with self.assertRaises(ValueError): evidence.compiler_profile_values(record,0)
        record["secondaryMetrics"]["compiler.time.profiled"]=dict(score=8,rawData=[[1]*8])
        self.assertEqual((8,[1]*8),evidence.compiler_profile_values(record,0))


if __name__=="__main__": unittest.main()
