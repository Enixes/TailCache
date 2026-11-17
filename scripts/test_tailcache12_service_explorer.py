import base64
import hashlib
import json
import re
import unittest
import tailcache12_service_explorer as ui


class FollowupExplorerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.offline=ui.render_component()
        cls.hosted=ui.render_component(hosted=True)

    def test_offline_package_is_exact_and_hosted_metadata_matches(self):
        pattern=r'<script id="sf-data" type="application/json">(.*?)</script>'
        raw=re.search(pattern,self.offline,re.S).group(1)
        self.assertEqual(raw,(ui.BASE/'followup-data-20261117.json').read_text())
        hosted=json.loads(re.search(pattern,self.hosted,re.S).group(1))
        self.assertNotIn('data',hosted['curves'])
        complete=json.loads(raw);hosted['curves']['data']=complete['curves']['data']
        self.assertEqual(hosted,complete)
        self.assertIn('data-package-url="service-data.json"',self.hosted)

    def test_current_result_review_claim_downloads_are_exact(self):
        links=re.findall(r'href="data:text/markdown;base64,([^"]+)" download="([^"]+)" data-sha256="([^"]+)"',self.offline)
        self.assertEqual(len(links),3)
        for encoded,name,digest in links:
            raw=base64.b64decode(encoded,validate=True)
            self.assertEqual(raw,(ui.BASE/name).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)

    def test_rebuild_is_idempotent_and_preserves_old_evidence(self):
        page='<html><body><main class="wrap"><p>historical evidence</p></main></body></html>'
        once=ui.attach(page,self.offline)
        self.assertEqual(once,ui.attach(once,self.offline))
        self.assertEqual(once.count('id="service-followup"'),1)
        self.assertIn('<p>historical evidence</p>',once)
        self.assertEqual(self.offline.count('<figure>'),7)


if __name__=='__main__':unittest.main()
