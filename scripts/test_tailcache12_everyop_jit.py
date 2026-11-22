import csv
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_everyop_jit as screen


class UnprofiledQualificationTest(unittest.TestCase):
    def test_actual_recorder_mode_requires_false_xml_controls_and_absent_xml_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt=pathlib.Path(directory)/"unprofiled-screen"
            attempt.mkdir()
            (attempt/"source.tar.gz").write_bytes(b"fixture-source")
            control=attempt/"fork1"
            control.mkdir()
            (control/"host.csv").write_text("monotonicNs\n1\n2\n")
            raw=attempt/"raw"
            worker=raw/"every-operation/worker"
            worker.mkdir(parents=True)
            config=worker/"configuration.txt"
            config.write_text("compilerXml=false\ncompilerCounters=true\n")
            (raw/"every-operation/gc-1.log").write_text("fixture-gc")
            with (worker/"iterations.csv").open("w",newline="") as stream:
                writer=csv.DictWriter(stream,["phase","startNs","endNs","compilerMs"])
                writer.writeheader()
                writer.writerow(dict(phase="WARMUP",startNs=1,endNs=10**9,compilerMs=0))
                for i in range(8): writer.writerow(dict(phase="MEASUREMENT",startNs=(i+1)*10**9,endNs=(i+2)*10**9,compilerMs=0))
            manifest=dict(stage="everyop-jit",compilerXml=False,sourceArchiveSha256=screen.calibration.sha(attempt/"source.tar.gz"),
                expectedBlocks=["fork1"],invocations=[dict(label="fork1",properties={})])
            (attempt/"manifest.json").write_text(json.dumps(manifest))
            with patch.object(screen.calibration,"verify_invocation",return_value=raw), \
                 patch.object(screen,"every_operation_fork_summary",return_value=dict(compilerPerIterationMs=[0]*8,rejectionReasons=[])) as parse, \
                 patch.object(screen.evidence,"replay_host_gate",return_value=([],0)):
                result=screen.replay(attempt)
                self.assertTrue(result["qualityPass"])
                self.assertFalse(result["compilerXml"])
                self.assertEqual("actual-unprofiled-recorder",result["qualificationChannel"])
                self.assertFalse(parse.call_args.kwargs["compiler_diagnostics"])
                xml=raw/"every-operation/jit-1.xml"
                xml.write_text("unexpected-profiler")
                with self.assertRaises(ValueError): screen.replay(attempt)
                xml.unlink()
                config.write_text("compilerXml=true\ncompilerCounters=true\n")
                with self.assertRaises(ValueError): screen.replay(attempt)


if __name__=="__main__": unittest.main()
