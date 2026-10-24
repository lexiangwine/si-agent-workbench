import unittest
from tools.quality_gate import scan_text, forbidden_path

class TestQualityGate(unittest.TestCase):
    def test_private_runtime_paths(self):
        for name in ('workspace/projects/p/brief.md', '.env', '.env.production', '.env.local.bak', 'config/providers.local.json'):
            self.assertTrue(forbidden_path(name), name)
        self.assertFalse(forbidden_path('.env.example'))
        self.assertFalse(forbidden_path('config/providers.example.json'))
    def test_private_key_detection(self):
        self.assertIn('private-key', scan_text('-----BEGIN ' + 'PRIVATE KEY-----'))
    def test_aws_key_detection(self):
        self.assertIn('aws-access-key', scan_text('AKIA'+'A'*16))
    def test_clean_file(self):
        self.assertEqual([], scan_text('Hello world, no credentials here.'))
    def test_github_token_detection(self):
        self.assertIn('github-token', scan_text('ghp_'+'A'*30))
if __name__=='__main__': unittest.main()
