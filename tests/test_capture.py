import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SPEC = importlib.util.spec_from_file_location("capture", Path(__file__).resolve().parents[1] / "scripts/capture.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


class CaptureTests(unittest.TestCase):
    def request(self, **options):
        return c.normalize_request({"scenes": [{"id": "test", **options}]})[0]

    def test_phone_and_tablet_use_different_layout_space(self):
        phone = self.request()
        tablet = self.request(device="tablet")
        self.assertEqual(480, phone["dpi"])
        self.assertEqual(320, tablet["dpi"])
        self.assertEqual(800, tablet["resolution"]["width"] * 160 / tablet["dpi"])

    def test_custom_resolution_is_not_changed(self):
        item = self.request(resolution={"width": 1024, "height": 2048})
        self.assertEqual({"width": 1024, "height": 2048}, item["resolution"])

    def test_rejects_misleading_device_configuration(self):
        with self.assertRaises(c.CaptureError):
            self.request(device="tablet", dpi=480, resolution={"width": 1080, "height": 2400})

    def test_rejects_unknown_and_bad_options(self):
        for fields in ({"theme": "auto"}, {"system_ui": "false"}, {"randomOption": 1}, {"mock": []}, {"locale": 'en"bad'}):
            with self.subTest(fields=fields), self.assertRaises(c.CaptureError):
                self.request(**fields)
        with self.assertRaises(c.CaptureError):
            c.normalize_request({"scenes": [{"id": "same"}, {"id": "same"}]})

    def test_mock_is_emitted_as_literals(self):
        self.assertEqual('"\\${Runtime.getRuntime()}"', c.kotlin('${Runtime.getRuntime()}'))
        self.assertIn("\\u000c", c.kotlin("a\fb"))
        self.assertIn("mapOf<String, Any?>", c.kotlin({"weather": {"temp": 18}, "items": [True, None]}))
        with self.assertRaises(c.CaptureError):
            c.kotlin(float("nan"))

    def test_locale_conversion(self):
        self.assertEqual("zh-rCN", c.preview_locale("zh-CN"))
        self.assertEqual("b+zh+Hant+TW", c.preview_locale("zh-Hant-TW"))

    def test_snapshot_does_not_touch_source_or_recurse_into_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "project"
            source.mkdir()
            (source / "Main.kt").write_text("real UI")
            (source / "build").mkdir()
            (source / "build/stale.png").write_bytes(b"stale")
            output = source / "output"
            output.mkdir()
            destination = output / "workspace"
            c.snapshot(source, destination)
            self.assertFalse((destination / "build").exists())
            self.assertFalse((destination / "output").exists())
            (destination / "Main.kt").write_text("adapter change")
            self.assertEqual("real UI", (source / "Main.kt").read_text())

    def test_generated_previews_apply_every_render_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = root / "adapter.kt"
            adapter.write_text("package demo\n@Composable fun CaptureScene(input: CaptureInput) {}")
            scene = self.request(theme="dark", locale="zh-CN", system_ui=True, mock={"city": "上海"})
            c.generate_previews(root / "generated", [scene], adapter)
            code = (root / "generated/GeneratedCaptures.kt").read_text()
            for text in ["spec:width=1080px,height=2400px,dpi=480", 'locale = "zh-rCN"', "showSystemUi = true", "UI_MODE_NIGHT_YES", '"city" to "上海"', "import demo.CaptureScene"]:
                self.assertIn(text, code)

    def test_native_png_dimensions_and_corruption_detection(self):
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.png"
            data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            data += chunk(b"IDAT", zlib.compress(b"\0\xff\xff\xff")) + chunk(b"IEND", b"")
            path.write_bytes(data)
            self.assertEqual((1, 1), c.png_size(path))
            path.write_bytes(data[:-4])
            with self.assertRaises(c.CaptureError):
                c.png_size(path)


if __name__ == "__main__":
    unittest.main()
