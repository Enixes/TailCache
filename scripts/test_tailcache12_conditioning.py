import csv
import json
import pathlib
import tempfile
import unittest

import tailcache12 as evidence
from tailcache12_study_analysis import jmh_fork_summary


class ConditioningTest(unittest.TestCase):
    def test_only_predeclared_analysis_histograms_supply_endpoints_and_all_phases_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            sample=root/"sample"
            sample.mkdir()
            inputs=dict(Backend="CAFFEINE",Payload=256,Residents=8192,LiveBytes=0,ChurnBytesPerSecond=1024,
                        Seed=24301,Warmups=12,Conditioning=8,Measurements=8,HeapMiB=512)
            runtime=dict(jmhVersion="1.37",jdkVersion="21",vmName="VM",vmVersion="build")
            record=dict(runtime,benchmark="io.github.enixes.tailcache.benchmark.CrossoverBenchmark.mixedWorkload",
                forks=1,threads=1,mode="sample",warmupIterations=12,measurementIterations=16,warmupTime="1 s",measurementTime="1 s",
                jvmArgs=["-Xms512m","-Xmx512m","-XX:+UseG1GC","-Dtailcache12.conditioningIterations=8"],
                params=dict(backend="CAFFEINE",payloadBytes="256",residentEntries="8192",applicationLiveBytes="0",
                            churnBytesPerSecond="1024",seed="24301"),secondaryMetrics={},
                primaryMetric=dict(scoreUnit="ns/op",rawDataHistogram=[[[[10240,12500]]]*8+[[[100,12500]]]*8],scorePercentiles={"99.9":10240}))
            trace="a"*64
            (sample/"jmh.txt").write_text(f"traceSha256={trace} valueGenerator=xorshift-key-version-v1 conditioningIterations=8\n[TailCache12][integrity]\n")
            rows=[]
            for phase,count in (("WARMUP",12),("CONDITIONING",8),("MEASUREMENT",8)):
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
            record["measurementIterations"]=16
            rows[12]["operations"]=100;write()
            with self.assertRaises(ValueError): analyze()
            rows[12]["operations"]=100000
            rows[12]["phase"],rows[20]["phase"]=rows[20]["phase"],rows[12]["phase"];write()
            with self.assertRaises(ValueError): analyze()
            rows[12]["phase"],rows[20]["phase"]=rows[20]["phase"],rows[12]["phase"]
            rows[20]["workerEnvelopeCompilerMs"]=11;write()
            self.assertFalse(analyze()["accepted"])

    def test_broad_compiler_gate_uses_fixed_analysis_count_and_preserves_legacy_count(self):
        record=dict(secondaryMetrics={"compiler.time.profiled":dict(score=800,rawData=[[99]*8+[1]*8])})
        total,values=evidence.compiler_profile_values(record,8)
        self.assertEqual((8,[1]*8),(total,values))
        with self.assertRaises(ValueError): evidence.compiler_profile_values(record,0)
        record["secondaryMetrics"]["compiler.time.profiled"]=dict(score=8,rawData=[[1]*8])
        self.assertEqual((8,[1]*8),evidence.compiler_profile_values(record,0))


if __name__=="__main__": unittest.main()
