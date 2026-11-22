import fcntl
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import tailcache12_native as launch


class NativeLauncherTest(unittest.TestCase):
    def test_exec_keeps_exact_scope_command_and_native_lock_options(self):
        with patch('sys.argv',['native','fixture','scripts/tailcache12_quiet.py','fixture-quiet']), \
             patch.object(launch.os,'execvpe') as execute,patch.object(launch.os,'chdir'):
            launch.main()
        program,command,environment=execute.call_args.args
        self.assertEqual(program,'flock')
        self.assertEqual(command[:5],['flock','--exclusive','--nonblock','--conflict-exit-code','73'])
        self.assertNotIn('--no-fork',command);self.assertNotIn('--close',command);self.assertNotIn('--fcntl',command)
        self.assertIn('--unit=tailcache12-fixture.scope',command)
        self.assertEqual(environment['TAILCACHE_REQUIRE_NATIVE_HOST'],'1')
        self.assertEqual(environment['TAILCACHE_NATIVE_SCOPE'],'tailcache12-fixture.scope')

    def test_native_holder_interoperates_with_python_archive_lock_and_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            lock=pathlib.Path(directory)/'lock'
            child=subprocess.Popen(['flock','--exclusive','--nonblock','--conflict-exit-code','73',str(lock),
                sys.executable,'-c','print("held",flush=True);input()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),'held')
                with lock.open('a') as handle:
                    with self.assertRaises(BlockingIOError):fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                result=subprocess.run(['flock','--exclusive','--nonblock','--conflict-exit-code','73',str(lock),
                    sys.executable,'-c','raise SystemExit(0)'])
                self.assertEqual(result.returncode,73)
                child.communicate('\n',timeout=10);self.assertEqual(child.returncode,0)
                with lock.open('a') as handle:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:
                if child.poll() is None:child.kill();child.communicate(timeout=5)


if __name__=='__main__':unittest.main()
