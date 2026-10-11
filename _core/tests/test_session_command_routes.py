"""Keep retired session CLI calls out of non-test repository files."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SessionCommandRouteTests(unittest.TestCase):
    def test_non_test_repo_files_have_no_retired_session_cli_calls(self):
        violations = []
        for path in ROOT.rglob("*"):
            relative = path.relative_to(ROOT)
            if ".git" in relative.parts or relative.parts[:2] == ("_core", "tests") or not path.is_file():
                continue
            if b"pplx session " in path.read_bytes():
                violations.append(str(relative))
        self.assertEqual(violations, [], f"Retired session CLI calls in {violations}")


if __name__ == "__main__":
    unittest.main()
