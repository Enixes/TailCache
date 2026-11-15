import base64
import hashlib
import pathlib
import re
import unittest
import tailcache12_review_explorer as review


class ReviewedExplorerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.component=review.render_component()

    def test_single_review_claim_and_figure_coverage(self):
        self.assertEqual(self.component.count('id="review-update"'),1)
        self.assertEqual(len(re.findall(r'<tr><th>C\d+',self.component)),14)
        self.assertEqual(self.component.count('<figure>'),7)
        self.assertIn('104 MiB: mixed',self.component)
        self.assertIn('remains NO_GO',self.component)

    def test_downloads_are_exact_current_files(self):
        links=re.findall(r'href="data:[^;]+;base64,([^\"]+)" download="([^\"]+)" data-sha256="([^\"]+)"',self.component)
        self.assertEqual(len(links),4)
        for encoded,name,digest in links:
            path=review.ROOT/'docs/preprint'/name
            if not path.exists():path=review.ROOT/'docs'/name
            content=base64.b64decode(encoded,validate=True)
            self.assertEqual(content,path.read_bytes())
            self.assertEqual(hashlib.sha256(content).hexdigest(),digest)

    def test_attachment_is_idempotent_and_preserves_historical_content(self):
        page='<html><body><main class="wrap"><p>retained evidence</p></main></body></html>'
        once=review.attach(page,self.component);twice=review.attach(once,self.component)
        self.assertEqual(once,twice)
        self.assertIn('<p>retained evidence</p>',twice)


if __name__=='__main__':unittest.main()
