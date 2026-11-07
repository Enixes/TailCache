import hashlib
import pathlib
import tempfile
import unittest

import tailcache12_sample_selection as selection


class SampleSelectionReplayTest(unittest.TestCase):
    def fixture(self, directory,version=selection.VERSION):
        source = directory / 'sample-selection-source'
        source.mkdir()
        for method in ('mixedWorkload', 'freshSupplyFloor'):
            name = 'CrossoverBenchmark_' + method + '_jmhTest'
            declaration = 'public final class ' + name + ' {'
            original = (declaration + '\nint rndMask = startRndMask;\nlong before=System.nanoTime();\n'
                '        int currentStride = 0;\n        do {\n'+selection.OLD+'\n'
                '            if (sample) {\n                time = System.nanoTime();\n            }\n'
                '            cacheOperation();\n            if (sample) {\n'
                '                buffer.add((System.nanoTime() - time) / opsPerInv);\n'+selection.ADAPTIVE+'\n            }\n'
                'long after=System.nanoTime();\n        startRndMask = Math.max(startRndMask, rndMask);\n'
                '        result.realTime = realTime;\n        result.measuredOps = operations;\n}')
            (source / ('original-' + name + '.java')).write_text(original)
            (source / ('overlay-' + name + '.java')).write_text(
                selection.transform(original,declaration,version))
        values = {}
        for part, data in (('harness', b'\xca\xfe\xba\xbeJmhSampleSelector'),
                           ('selector', b'\xca\xfe\xba\xbe' + version.encode())):
            (directory / ('sample-' + part + '-123.class')).write_bytes(data)
            values[part] = hashlib.sha256(data).hexdigest()
        origin='tailcache12-dense-sampler' if version==selection.DENSE_VERSION else 'tailcache12-sampler'
        props = ('sampleSelectionVersion=' + version + '\nharnessClass=' + selection.PACKAGE
                 + 'CrossoverBenchmark_mixedWorkload_jmhTest\nharnessOrigin=file:/host/classes/'+origin+'/\n'
                 + 'harnessSha256=' + values['harness'] + '\nselectorSha256=' + values['selector'] + '\n')
        (directory / 'sample-selection-123.properties').write_text(props)
        return (' sampleSelectionVersion=' + version + ' sampleHarnessSha256=' + values['harness']
                + ' sampleSelectorSha256=' + values['selector'])

    def test_actual_record_bytes_and_only_declared_source_diff_required(self):
        for mutation in ('none', 'class', 'boundary', 'missing-proof'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                directory = pathlib.Path(temporary)
                text = self.fixture(directory)
                args = ['-Dtailcache12.sampleSelectionVersion=' + selection.VERSION]
                if mutation == 'class':
                    (directory / 'sample-harness-123.class').write_bytes(b'changed')
                elif mutation == 'boundary':
                    path = directory / 'sample-selection-source/overlay-CrossoverBenchmark_mixedWorkload_jmhTest.java'
                    path.write_text(path.read_text().replace('long before=System.nanoTime();', 'long before=0;'))
                elif mutation == 'missing-proof':
                    (directory / 'sample-selection-123.properties').unlink()
                if mutation == 'none':
                    self.assertTrue(selection.verify(directory, args, text, 'mixedWorkload')['modifiedGeneratedSampler'])
                    with self.assertRaises(ValueError): selection.verify(directory, args, text, 'freshSupplyFloor')
                else:
                    with self.assertRaises(ValueError): selection.verify(directory, args, text, 'mixedWorkload')

    def test_legacy_is_not_relabelled_and_declared_missing_overlay_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            self.assertIsNone(selection.verify(directory, [], 'original JMH', 'mixedWorkload'))
            with self.assertRaises(ValueError):
                selection.verify(directory, ['-Dtailcache12.sampleSelectionVersion=' + selection.VERSION], '', 'mixedWorkload')

    def test_historical_adaptive_overlay_still_replays_and_fixed_mask_cannot_adapt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=pathlib.Path(temporary)
            text=self.fixture(directory,selection.LEGACY_VERSION)
            row=selection.verify(directory,['-Dtailcache12.sampleSelectionVersion='+selection.LEGACY_VERSION],text,'mixedWorkload')
            self.assertTrue(row['adaptiveDecimation'])
        for mutation in ('mask','half'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temporary:
                directory=pathlib.Path(temporary);text=self.fixture(directory)
                path=directory/'sample-selection-source/overlay-CrossoverBenchmark_mixedWorkload_jmhTest.java'
                content=path.read_text()
                content=content.replace('int rndMask = 15;','int rndMask = 31;') if mutation=='mask' else content.replace('long after=System.nanoTime();','long after=System.nanoTime();buffer.half();')
                path.write_text(content)
                with self.assertRaises(ValueError):selection.verify(directory,['-Dtailcache12.sampleSelectionVersion='+selection.VERSION],text,'mixedWorkload')

    def test_common_observer_keeps_selected_end_after_existing_predicate_and_record_outside(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=pathlib.Path(temporary);text=self.fixture(directory,selection.DENSE_VERSION)
            row=selection.verify(directory,['-Dtailcache12.sampleSelectionVersion='+selection.DENSE_VERSION],text,'mixedWorkload')
            self.assertTrue(row['denseObserverWork']);self.assertFalse(row['adaptiveDecimation'])
            path=directory/'sample-selection-source/overlay-CrossoverBenchmark_mixedWorkload_jmhTest.java'
            source=path.read_text()
            self.assertIn('if (sample) {\n                denseEnd = System.nanoTime();',source)
            self.assertLess(source.index('cacheOperation();'),source.index('denseEnd = System.nanoTime();'))
            self.assertLess(source.index('denseEnd = System.nanoTime();'),source.index('recordDense('))
            path.write_text(source.replace('cacheOperation();','recordDense(0,0,0);cacheOperation();'))
            with self.assertRaises(ValueError):selection.verify(directory,['-Dtailcache12.sampleSelectionVersion='+selection.DENSE_VERSION],text,'mixedWorkload')


if __name__ == '__main__':
    unittest.main()
