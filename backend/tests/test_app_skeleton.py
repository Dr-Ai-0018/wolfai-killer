import importlib
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AppSkeletonTests(unittest.TestCase):
    def test_backend_app_package_documents_scaffold_status(self):
        package = importlib.import_module("app")

        self.assertIn("当前实际运行入口仍是 backend/app.py", package.__doc__)

    def test_router_package_only_exports_available_router(self):
        routers = importlib.import_module("app.routers")

        self.assertEqual(routers.__all__, ["admin_router"])
        self.assertTrue(hasattr(routers, "admin_router"))
        self.assertFalse(hasattr(routers, "game_router"))
        self.assertFalse(hasattr(routers, "stats_router"))
