import hashlib
import pathlib
import tempfile
import unittest

import tailcache12_sample_selection as selection


class SampleSelectionReplayTest(unittest.TestCase):
    def fixture(self, directory):
        source = directory / 'sample-selection-source'
        source.mkdir()
        for method in ('mixedWorkload', 'freshSupplyFloor'):
            name = 'CrossoverBenchmark_' + method + '_jmhTest'
            declaration = 'public final class ' + name + ' {'
            original = declaration + '\nlong before=System.nanoTime();\n' + selection.OLD + '\nlong after=System.nanoTime();\n}'
            (source / ('original-' + name + '.java')).write_text(original)
            (source / ('overlay-' + name + '.java')).write_text(
                original.replace(selection.OLD, selection.NEW).replace(declaration, declaration + selection.MARKER))
        values = {}
        for part, data in (('harness', b'\xca\xfe\xba\xbeJmhSampleSelector'),
                           ('selector', b'\xca\xfe\xba\xbe' + selection.VERSION.encode())):
            (directory / ('sample-' + part + '-123.class')).write_bytes(data)
            values[part] = hashlib.sha256(data).hexdigest()
        props = ('sampleSelectionVersion=' + selection.VERSION + '\nharnessClass=' + selection.PACKAGE
                 + 'CrossoverBenchmark_mixedWorkload_jmhTest\nharnessOrigin=file:/host/classes/tailcache12-sampler/\n'
                 + 'harnessSha256=' + values['harness'] + '\nselectorSha256=' + values['selector'] + '\n')
        (directory / 'sample-selection-123.properties').write_text(props)
        return (' sampleSelectionVersion=' + selection.VERSION + ' sampleHarnessSha256=' + values['harness']
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


if __name__ == '__main__':
    unittest.main()
