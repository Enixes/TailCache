import hashlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest
import tailcache12 as evidence
import tailcache12_calibrate as calibration

from tailcache12_jfr import event_stream, recording_file, validate_instrumentation, verify_metadata
from tailcache12_profile_probe import grid
from unittest.mock import patch
from types import SimpleNamespace
from tailcache12_jfr import verify_single_chunk,gc_clock_alignment,wall_to_monotonic,epoch_ns


class WorkerProfileTest(unittest.TestCase):
    def test_large_artifact_hashing_never_reads_a_whole_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=pathlib.Path(temporary)/'recording';data=b'bounded-recording'*200000;path.write_bytes(data)
            expected=hashlib.sha256(data).hexdigest()
            with patch.object(pathlib.Path,'read_bytes',side_effect=AssertionError('whole-file allocation')):
                self.assertEqual(evidence.file_sha(path),expected)
                self.assertEqual(calibration.sha(path),expected)

    def test_affine_clock_uses_held_out_anchors_and_keeps_nanosecond_timezone_precision(self):
        self.assertEqual(epoch_ns('1970-01-01T05:30:00.123456789+05:30'),123456789)
        def stamp(ns):
            return datetime.datetime.fromtimestamp(ns//10**9,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{ns%10**9:09d}Z'
        pauses=[dict(gcId=str(i),kind='Pause Young',startNs=10**9*(i+1)) for i in range(9)]
        events=[dict(type='jdk.GarbageCollection',values=dict(gcId=i,startTime=stamp(10**15+1004*10**6*(i+1)))) for i in range(9)]
        clock=gc_clock_alignment(events,pauses)
        self.assertEqual(clock['discardedAnchors'],0)
        self.assertLess(clock['maximumHeldOutResidualNs'],1)
        self.assertEqual(wall_to_monotonic(10**15+1004*10**6*5,clock),5*10**9)

    def test_multichunk_or_failed_recording_export_is_inconclusive(self):
        for count,code in ((1,0),(2,0),(1,1)):
            with self.subTest(count=count,code=code),tempfile.TemporaryDirectory() as temporary:
                destination=pathlib.Path(temporary)
                with patch('tailcache12_jfr.subprocess.run',return_value=SimpleNamespace(
                        stdout=f'Chunks: {count}\n',stderr='',returncode=code)):
                    if count==1 and code==0:
                        self.assertEqual(verify_single_chunk('jfr','worker.jfr',destination)['chunks'],1)
                    else:
                        with self.assertRaises(ValueError):verify_single_chunk('jfr','worker.jfr',destination)

    def test_four_fresh_diagnostic_slots_and_no_other_backend(self):
        slots=grid()
        self.assertEqual(len(slots),4)
        self.assertEqual([p['Channel'] for _,p in slots],
            ['sample-calibration','every-operation','every-operation','sample-calibration'])
        for _,props in slots:
            self.assertEqual(props['Backend'],'CHRONICLE_IN_MEMORY')
            self.assertEqual(props['FlightRecorder'],'true')
            self.assertEqual(props['DiagnosticOnly'],'true')

    def test_recording_identity_loss_clock_and_full_window_coverage_fail_closed(self):
        def stamp(ns):
            return datetime.datetime.fromtimestamp(ns//10**9,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{ns%10**9:09d}Z'
        offset=10**15
        gc=[dict(gcId=str(i),kind='Pause Young',startNs=n) for i,n in enumerate((70*10**9,120_200_000_000,120_800_000_000))]
        events=[dict(type='jdk.JVMInformation',values=dict(pid=7,javaArguments='worker',startTime=stamp(offset)))]
        events += [dict(type='jdk.GarbageCollection',values=dict(gcId=int(p['gcId']),startTime=stamp(offset+p['startNs']))) for p in gc]
        events += [dict(type='jdk.Shutdown',values=dict(startTime=stamp(offset+122*10**9)))]
        windows=[(120*10**9,121*10**9)]
        self.assertTrue(verify_metadata(events,7,'worker',gc,windows)['metadataPass'])
        identified=json.loads(json.dumps(events));identified[0]['values'].update(jvmName='Exact VM',jvmVersion='Exact VM (21.0.12.1+1) for linux')
        self.assertTrue(verify_metadata(identified,7,'worker',gc,windows,
            runtime_identity=dict(vmName='Exact VM',vmVersion='21.0.12.1+1'))['metadataPass'])
        with self.assertRaises(ValueError):verify_metadata(identified,7,'worker',gc,windows,
            runtime_identity=dict(vmName='Exact VM',vmVersion='21.0.12.1+2'))
        for wrong in (events[:-1],events+[dict(type='jdk.DataLoss',values={})]):
            with self.assertRaises(ValueError):verify_metadata(wrong,7,'worker',gc,windows)
        with self.assertRaises(ValueError):verify_metadata(events,8,'worker',gc,windows)
        with self.assertRaises(ValueError):verify_metadata(events,7,'other-main',gc,windows)
        with self.assertRaises(ValueError):verify_metadata(events,7,'worker',gc,[(120*10**9,123*10**9)])
        changed=json.loads(json.dumps(events));changed[3]['values']['startTime']=stamp(offset+gc[2]['startNs']+3_000_000)
        with self.assertRaises(ValueError):verify_metadata(changed,7,'worker',gc,windows)
    def test_fragmented_nested_jdk_event_stream_is_bounded(self):
        events=[dict(type='jdk.Test',values={'frames':[{'text':'escaped "[,]" {nested}'}]}),
                dict(type='jdk.Test2',values={})]
        text=json.dumps({'recording':{'events':events}})
        for size in (1,7,65536):
            self.assertEqual(list(event_stream(io.StringIO(text),chunk_chars=size)),events)
        with self.assertRaises(ValueError):
            list(event_stream(io.StringIO(text),chunk_chars=7,maximum_event_chars=60))
        for changed in (text[:-3],text.replace('"recording"','"unknown"'),text.replace('}, {','} {'),
                        '{"recording":{"events":[{"type":"x","values":{}},]}}'):
            with self.assertRaises(ValueError):list(event_stream(io.StringIO(changed),chunk_chars=1))

    def test_flight_recording_is_explicitly_excluded_from_ordinary_endpoints(self):
        flags=['-XX:StartFlightRecording=settings=actual.jfc','-XX:FlightRecorderOptions=maxchunksize=256m,stackdepth=64']
        inputs=dict(FlightRecorder='true',DiagnosticOnly='true')
        validate_instrumentation([],{},False)
        validate_instrumentation(flags,inputs,True)
        for args,props,allowed in ((flags,{},False),(flags,inputs,False),([],inputs,True),
                                   (flags,dict(FlightRecorder='true'),True),(flags+flags,inputs,True)):
            with self.assertRaises(ValueError):validate_instrumentation(args,props,allowed)

    def test_unique_recording_and_exact_settings_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);(root/'jfr').mkdir();settings=root/'flight-recorder.jfc'
            settings.write_text('settings');digest=hashlib.sha256(settings.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):recording_file(root,digest)
            target=root/'jfr/worker.jfr';target.write_bytes(b'recording')
            self.assertEqual(recording_file(root,digest),target)
            settings.write_text('changed')
            with self.assertRaises(ValueError):recording_file(root,digest)
            settings.write_text('settings');(root/'jfr/extra.jfr').write_bytes(b'extra')
            with self.assertRaises(ValueError):recording_file(root,digest)


if __name__=='__main__':unittest.main()
