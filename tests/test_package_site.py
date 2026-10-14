import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_site.py"
SPEC = importlib.util.spec_from_file_location("package_site", SCRIPT)
package_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_site)


class PackageSiteTests(unittest.TestCase):
    def test_package_is_a_full_fresh_copy_of_deployable_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "site"
            outputs = root / "outputs"
            source.mkdir()
            outputs.mkdir()
            (source / "server.py").write_text("latest server", encoding="utf-8")
            (source / "favicon.svg").write_text("flower", encoding="utf-8")
            (source / "data").mkdir()
            (source / "data" / "family.sqlite3").write_text("private", encoding="utf-8")
            (source / ".env").write_text("SECRET=value", encoding="utf-8")
            (source / "__pycache__").mkdir()
            (source / "__pycache__" / "server.pyc").write_bytes(b"cache")
            existing = outputs / "family-site"
            existing.mkdir()
            (existing / "removed-from-source.txt").write_text("stale", encoding="utf-8")

            folder, archive = package_site.build_deployment_package(source, outputs)

            self.assertEqual((folder / "server.py").read_text(encoding="utf-8"), "latest server")
            self.assertEqual((folder / "favicon.svg").read_text(encoding="utf-8"), "flower")
            self.assertFalse((folder / "removed-from-source.txt").exists())
            packaged_files = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
            self.assertEqual(packaged_files, {"server.py", "favicon.svg"})
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), packaged_files)
                self.assertEqual(bundle.read("server.py"), b"latest server")


if __name__ == "__main__":
    unittest.main()

