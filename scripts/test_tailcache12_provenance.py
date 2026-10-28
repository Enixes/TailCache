import pathlib
import tarfile
import tempfile
import unittest

from tailcache12_provenance import CONTROLS, archive_measurement_source_hash, measurement_source_hash


class MeasurementProvenanceTest(unittest.TestCase):
    def test_analysis_changes_preserve_identity_but_java_and_build_changes_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "source"
            for name in (*CONTROLS, "src/main/java/A.java", "src/jmh/java/B.java", "gradle/wrapper/w.properties"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            snapshot = pathlib.Path(directory) / "source.tar.gz"
            with tarfile.open(snapshot, "w:gz") as archive:
                for path in root.rglob("*"):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(root).as_posix())
            original = measurement_source_hash(root)
            self.assertEqual(original, archive_measurement_source_hash(snapshot))
            (root / "scripts/analysis.py").write_text("new analysis")
            self.assertEqual(original, measurement_source_hash(root))
            (root / "src/main/java/A.java").write_text("changed workload")
            self.assertNotEqual(original, measurement_source_hash(root))
            (root / "src/main/java/A.java").write_text("src/main/java/A.java")
            (root / "scripts/tailcache12_controller.py").write_text("changed launch schedule")
            self.assertNotEqual(original, measurement_source_hash(root))
            (root / "scripts/tailcache12_controller.py").write_text("scripts/tailcache12_controller.py")
            (root / "build.gradle.kts").write_text("changed JVM flags")
            self.assertNotEqual(original, measurement_source_hash(root))

    def test_incomplete_archive_cannot_supply_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = pathlib.Path(directory) / "empty.tar.gz"
            with tarfile.open(snapshot, "w:gz"):
                pass
            with self.assertRaises(ValueError):
                archive_measurement_source_hash(snapshot)
