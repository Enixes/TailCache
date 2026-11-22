import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import tailcache12_tool_cache as tool


class ToolCacheTest(unittest.TestCase):
    def test_browser_enumeration_selects_installation_not_other_cache_or_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);code=root/'codex';code.write_bytes(b'code');browser=root/'browser';browser.mkdir()
            installed=browser/'chromium-123/chrome';installed.parent.mkdir();installed.write_bytes(b'browser code')
            personal=browser/'user-data/Cookies';personal.parent.mkdir();personal.write_bytes(b'not read')
            (browser/'registry.json').write_bytes(b'not selected')
            with patch.object(tool,'EXACT',(code,)),patch.object(tool,'BROWSER',browser):
                self.assertEqual(set(tool.targets()),{code,installed})
                link=root/'link';link.symlink_to(code)
                with patch.object(tool,'EXACT',(link,)):
                    with self.assertRaises(ValueError):tool.targets()

    def test_exact_tooling_policy_excludes_databases_credentials_jdk_and_user_data(self):
        for name in tool.EXACT:self.assertTrue(tool.allowed(str(name)))
        self.assertTrue(tool.allowed('/home/y/.cache/ms-playwright/chromium-123/chrome-linux/chrome'))
        for name in ('/home/y/.codex/auth.json','/home/y/.codex/logs_2.sqlite','/usr/lib/jvm/java-21-openjdk/lib/modules',
                     '/home/y/.cache/ms-playwright/user-data/Cookies','/home/y/.cache/ms-playwright/chromium-123/Default/History',
                     '/home/y/.cache/ms-playwright/chromium-123/../outside'):
            self.assertFalse(tool.allowed(name))

    def test_readonly_advice_preserves_bytes_and_receipt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);path=root/'code';path.write_bytes(b'preserved code');report=root/'receipt.json'
            with patch.object(tool,'EXACT',(path,)),patch.object(tool,'targets',return_value=[path]), \
                 patch.object(tool,'active_browsers',return_value=[]),patch.object(tool.evidence,'source_hash',return_value='source'), \
                 patch.object(tool,'memory_snapshot',return_value={'MemFreeKiB':1,'SwapUsedKiB':0}), \
                 patch.object(tool.os,'posix_fadvise') as advice:
                result=tool.prepare(report);self.assertTrue(tool.verify(result,'source'));advice.assert_called_once()
                with self.assertRaises(ValueError):tool.prepare(report)
                for mutation in ('source','path','owner','advice','size'):
                    changed=copy.deepcopy(result)
                    if mutation=='source':changed['sourceSha256']='other'
                    elif mutation=='path':changed['files'][0]['path']='/etc/passwd'
                    elif mutation=='owner':changed['files'][0]['uid']+=1
                    elif mutation=='advice':changed['files'][0]['advice']='GLOBAL_DROP'
                    else:changed['files'][0]['bytesAfter']=0
                    with self.assertRaises(ValueError):tool.verify(changed,'source')
            self.assertEqual(path.read_bytes(),b'preserved code')
            self.assertTrue(json.loads(report.read_text())['readOnly'])

    def test_active_browser_stops_before_advice_and_preserves_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'receipt.json'
            with patch.object(tool,'targets',return_value=[]),patch.object(tool,'active_browsers',return_value=[123]), \
                 patch.object(tool.evidence,'source_hash',return_value='source'),patch.object(tool.os,'posix_fadvise') as advice:
                with self.assertRaises(ValueError):tool.prepare(path)
            advice.assert_not_called();self.assertFalse(json.loads(path.read_text())['preparationPass'])


if __name__=='__main__':unittest.main()
