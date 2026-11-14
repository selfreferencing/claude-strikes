import os
import tempfile
import unittest
from unittest import mock

from strike import keys
from strike.keys import MissingKey, load_key

FAKE = "sk-or-v1-" + "0123456789abcdef" * 4


class LoadKeyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        env = mock.patch.dict(os.environ, {keys.KEY_DIR_ENV: self.dir}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(keys.ENV_VAR, None)

    def write(self, text, mode=0o600, name="free-systems.key"):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, mode)
        return path

    def assertRefused(self, fragment, **kw):
        with self.assertRaises(MissingKey) as ctx:
            load_key("free-systems", **kw)
        self.assertIn(fragment, str(ctx.exception))
        self.assertNotIn(FAKE, str(ctx.exception))

    def test_reads_the_labels_own_file(self):
        self.write(FAKE + "\n")
        key, source = load_key("free-systems")
        self.assertEqual(key, FAKE)
        self.assertNotIn(FAKE, source)
        self.assertTrue(source.endswith("free-systems.key"))

    def test_each_label_has_its_own_file(self):
        self.write(FAKE, name="ihs-agentic-capital.key")
        self.assertRefused("No key for 'free-systems'")

    def test_file_readable_by_others_refused(self):
        self.write(FAKE, mode=0o644)
        self.assertRefused("chmod 600")

    def test_bad_contents_refused(self):
        for text, fragment in (("", "empty"), ("Key: " + FAKE, "more than the key"),
                               (FAKE + "\n" + FAKE, "more than the key"), ("https://openrouter.ai/keys", "does not look")):
            with self.subTest(text=text[:12]):
                self.write(text)
                self.assertRefused(fragment)

    def test_file_wins_over_environment(self):
        self.write(FAKE)
        with mock.patch.dict(os.environ, {keys.ENV_VAR: "sk-or-v1-other"}):
            self.assertEqual(load_key("free-systems")[0], FAKE)

    def test_environment_as_fallback(self):
        with mock.patch.dict(os.environ, {keys.ENV_VAR: FAKE}):
            key, source = load_key("free-systems")
        self.assertEqual((key, source), (FAKE, "the OPENROUTER_API_KEY environment variable"))

    def test_default_folder_without_the_override(self):
        os.environ.pop(keys.KEY_DIR_ENV)
        self.assertTrue(keys.key_path("x").startswith(os.path.join("~", ".config", "strike-pilot")))

    def test_explicit_path(self):
        path = self.write(FAKE, name="elsewhere.key")
        self.assertEqual(load_key("free-systems", path)[0], FAKE)
        self.assertRefused("does not exist", path=os.path.join(self.dir, "missing.key"))


class SuiteIsolationTest(unittest.TestCase):
    def test_no_test_can_find_a_real_key(self):
        # Set in tests/__init__.py: the real key folder is never consulted during tests.
        self.assertIn("have-no-keys", os.environ.get(keys.KEY_DIR_ENV, ""))
        self.assertNotIn(keys.ENV_VAR, os.environ)
        with self.assertRaises(MissingKey):
            load_key("free-systems")


if __name__ == "__main__":
    unittest.main()
