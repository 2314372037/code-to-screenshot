#!/usr/bin/env python3
"""Render actual Compose previews with Google's Layoutlib screenshot engine. Python 3.11+."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import tomllib
import zlib

ENGINE = "0.0.1-alpha16"
PACKAGE = "dev.codetoscreenshot.generated"
SKIP = {".git", ".gradle", ".idea", ".kotlin", ".artifacts", "build", ".cxx", ".externalNativeBuild", "node_modules", "__pycache__"}


class CaptureError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise CaptureError(message)


def kotlin(value):
    """Data is emitted as literals, never interpolated as executable Kotlin."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False).replace("$", "\\$").replace("\\f", "\\u000c")
    if isinstance(value, int):
        require(-(2**63) < value < 2**63, "Mock integer is outside Kotlin Long range")
        return str(value) + ("L" if not -(2**31) <= value < 2**31 else "")
    if isinstance(value, float):
        require(math.isfinite(value), "Mock numbers must be finite")
        return repr(value)
    if isinstance(value, list):
        return "listOf<Any?>(" + ", ".join(kotlin(v) for v in value) + ")"
    if isinstance(value, dict):
        return "mapOf<String, Any?>(" + ", ".join(kotlin(k) + " to " + kotlin(v) for k, v in value.items()) + ")"
    raise CaptureError(f"Unsupported mock value: {type(value).__name__}")


def normalize_request(raw):
    require(isinstance(raw, dict) and raw.get("schema_version", 1) == 1, "Expected schema_version 1")
    require(set(raw) <= {"schema_version", "defaults", "scenes"}, "Unknown request field; see references/request.md")
    defaults = raw.get("defaults", {})
    require(isinstance(defaults, dict), "defaults must be an object")
    scenes = raw.get("scenes")
    require(isinstance(scenes, list) and 1 <= len(scenes) <= 24, "Provide 1–24 scenes per capture")
    output, ids = [], set()
    allowed = {"id", "locale", "theme", "device", "resolution", "dpi", "system_ui", "mock", "font_scale"}
    for index, item in enumerate(scenes):
        require(isinstance(item, dict), "Every scene must be an object")
        s = {**defaults, **item}
        require(set(s) <= allowed, f"Unknown scene fields: {set(s) - allowed}")
        ident = s.get("id", f"scene-{index + 1}")
        require(isinstance(ident, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", ident), "Scene id must be a safe lowercase filename")
        require(ident not in ids, f"Duplicate scene id: {ident}")
        ids.add(ident)
        device = s.get("device", "phone")
        require(device in ("phone", "tablet"), "device must be phone or tablet")
        res = s.get("resolution", {"width": 1080, "height": 2400} if device == "phone" else {"width": 1600, "height": 2560})
        require(isinstance(res, dict) and set(res) == {"width", "height"}, "resolution needs width and height in pixels")
        w, h = res["width"], res["height"]
        require(all(type(v) is int and 160 <= v <= 8192 for v in (w, h)) and w * h <= 24000000,
                "Resolution must be 160–8192 pixels per edge, at most 24 megapixels")
        dpi = s.get("dpi", round(min(w, h) * 160 / (360 if device == "phone" else 800)))
        require(type(dpi) is int and 72 <= dpi <= 960, "dpi must be 72–960; supply dpi explicitly for unusual resolutions")
        short_dp = min(w, h) * 160 / dpi
        require((short_dp < 600) == (device == "phone"), "dpi/resolution conflicts with phone (<600dp) or tablet (>=600dp) layout")
        theme = s.get("theme", "light")
        require(theme in ("light", "dark"), "theme must be light or dark")
        locale = s.get("locale", "en-US")
        require(isinstance(locale, str) and re.fullmatch(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*", locale), "locale must be a BCP-47 tag, e.g. zh-CN or zh-Hant-TW")
        system_ui = s.get("system_ui", False)
        require(type(system_ui) is bool, "system_ui must be true or false (status and navigation bars together)")
        mock = s.get("mock", {})
        require(isinstance(mock, dict), "mock must be an object")
        kotlin(mock)  # Validate finite and representable values now, before touching the project.
        font_scale = s.get("font_scale", 1.0)
        require(type(font_scale) in (int, float) and 0.5 <= font_scale <= 2.0, "font_scale must be 0.5–2.0")
        output.append(dict(id=ident, locale=locale, theme=theme, device=device, resolution=res, dpi=dpi,
                           system_ui=system_ui, font_scale=float(font_scale), mock=mock,
                           method=f"Capture_{index:03d}_{ident.replace('-', '_')}" + ("__system_ui_" + theme if system_ui else "")))
    return output


def preview_locale(locale):
    parts = locale.split("-")
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2 and len(parts[1]) in (2, 3):
        return parts[0] + "-r" + parts[1]
    return "b+" + "+".join(parts)


def walk_sources(root):
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP and not Path(base, d).is_symlink()]
        for name in files:
            p = Path(base, name)
            if p.suffix in (".kt", ".kts", ".gradle", ".toml"):
                yield p


def inspect_project(project, module):
    project = Path(project).resolve()
    require(re.fullmatch(r":?[A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)*", module), "Use a Gradle module path such as app or :feature:weather")
    module_dir = project.joinpath(*module.strip(":").split(":")).resolve()
    require(module_dir.is_relative_to(project), "Module must be inside project")
    build = next((p for p in [module_dir / "build.gradle.kts", module_dir / "build.gradle"] if p.is_file()), None)
    require(build is not None, f"No Android module build file at {module_dir}")
    require((project / "gradle/wrapper/gradle-wrapper.jar").is_file(), "Project needs a Gradle wrapper JAR")
    versions = {}
    catalog = project / "gradle/libs.versions.toml"
    if catalog.exists():
        versions = tomllib.loads(catalog.read_text(encoding="utf-8-sig")).get("versions", {})
    agp = versions.get("agp")
    if not agp:
        for p in [build, project / "build.gradle.kts", project / "build.gradle"]:
            if p.exists():
                match = re.search(r'''id\s*\(?["']com\.android\.(?:application|library)["']\)?\s*version\s*["']([^"']+)''', p.read_text(encoding="utf-8-sig"))
                if match:
                    agp = match[1]
                    break
    previews = []
    for p in walk_sources(module_dir / "src"):
        if p.suffix != ".kt":
            continue
        text = p.read_text(encoding="utf-8-sig")
        if "@Preview" in text:
            previews.append(str(p.relative_to(project)))
    return {"project": str(project), "module": ":" + module.strip(":"), "build_file": str(build.relative_to(project)),
            "agp": agp, "versions": versions, "preview_files": previews}


def snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    require(destination != source and not source.is_relative_to(destination), "Snapshot cannot contain or replace the source project")
    def ignore(folder, names):
        result = []
        for name in names:
            p = Path(folder, name)
            if name in SKIP or name.startswith("screenshotTest") or p.resolve() == destination or destination.is_relative_to(p.resolve()):
                result.append(name)
            elif p.is_symlink():
                raise CaptureError(f"Snapshot requires an explicit copy of symlinked source: {p}")
        return result
    shutil.copytree(source, destination, ignore=ignore)


def configure_build(workspace, info, backend, engine, variant):
    require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", variant), "Invalid build variant")
    require(re.fullmatch(r"[0-9A-Za-z.\-]+", engine), "Invalid engine version")
    path = workspace / info["build_file"]
    require(path.suffix == ".kts", "First release supports Kotlin Gradle DSL; convert the isolated module script or supply a Kotlin DSL capture harness")
    text = path.read_text(encoding="utf-8-sig")
    require("screenshotTests.create" not in text, "Existing native test suite needs an explicit isolated-project adaptation; do not duplicate it")
    if backend == "legacy":
        # Avoid inventing an alias or rewriting arbitrary Gradle blocks.
        has_plugin = 'id("com.android.compose.screenshot")' in text
        if not has_plugin:
            catalog = workspace / "gradle/libs.versions.toml"
            if catalog.exists():
                plugins = tomllib.loads(catalog.read_text(encoding="utf-8-sig")).get("plugins", {})
                for alias, value in plugins.items():
                    if isinstance(value, dict) and value.get("id") == "com.android.compose.screenshot":
                        accessor = "libs.plugins." + alias.replace("-", ".").replace("_", ".")
                        has_plugin = f"alias({accessor})" in text
        if not has_plugin:
            text, count = re.subn(r"\bplugins\s*\{", 'plugins {\n    id("com.android.compose.screenshot") version "' + engine + '"', text, count=1)
            require(count == 1, "No plugins {} block found in module build script")
        text += f'''\n// code-to-screenshot: isolated capture configuration
android {{ experimentalProperties["android.experimental.enableScreenshotTest"] = true }}
dependencies {{
    add("screenshotTestImplementation", "com.android.tools.screenshot:screenshot-validation-api:{engine}")
    add("screenshotTestImplementation", "androidx.compose.ui:ui-tooling")
}}
'''
        task = f"{info['module']}:update{variant[0].upper() + variant[1:]}ScreenshotTest"
        ref = "screenshotTest" + variant[0].upper() + variant[1:]
    else:
        require("com.android.compose.screenshot" not in text and "libs.plugins.screenshot" not in text,
                "Native suites cannot coexist with the standalone plugin; adapt only the isolated build")
        text += f'''\n// code-to-screenshot: isolated capture configuration
android {{
    testOptions {{
        screenshotTests.create("screenshotTest") {{
            engineVersion = "{engine}"
            targetVariants.add("{variant}")
            dependencies {{
                implementation("androidx.compose.ui:ui-tooling")
                implementation("com.android.tools.screenshot:screenshot-validation-api:{engine}")
            }}
        }}
    }}
}}
'''
        suffix = "Default" + variant[0].upper() + variant[1:]
        task = f"{info['module']}:updateScreenshotTest{suffix}TestSuite"
        ref = "screenshotTest" + suffix
    path.write_text(text, encoding="utf-8")
    properties = workspace / "gradle.properties"
    with properties.open("a", encoding="utf-8") as handle:
        handle.write("\nandroid.experimental.enableScreenshotTest=true\nandroid.compose.screenshot.maxHeapSize=3g\n")
        if backend == "suites":
            handle.write("android.experimental.testSuiteSupport=true\n")
    return task, path.parent / "src" / ref / "reference"


def generate_previews(directory, scenes, adapter):
    directory.mkdir(parents=True, exist_ok=True)
    text = Path(adapter).read_text(encoding="utf-8-sig")
    package = re.search(r"(?m)^\s*package\s+([\w.]+)", text)
    require(package and re.search(r"\bfun\s+CaptureScene\s*\(", text), "Adapter must define a package and @Composable fun CaptureScene(input: CaptureInput)")
    shutil.copyfile(adapter, directory / "CaptureScene.kt")
    runtime = '''package dev.codetoscreenshot.generated
data class CaptureInput(val id: String, val locale: String, val dark: Boolean, val mock: Map<String, Any?>) {
    fun text(key: String, fallback: String = "") = mock[key] as? String ?: fallback
    fun number(key: String, fallback: Double = 0.0) = (mock[key] as? Number)?.toDouble() ?: fallback
    fun flag(key: String, fallback: Boolean = false) = mock[key] as? Boolean ?: fallback
}
'''
    (directory / "CaptureInput.kt").write_text(runtime, encoding="utf-8")
    source = f'''package {PACKAGE}
import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import {package[1]}.CaptureScene
'''
    for scene in scenes:
        w, h = scene["resolution"]["width"], scene["resolution"]["height"]
        device = f"spec:width={w}px,height={h}px,dpi={scene['dpi']}"
        source += f'''
@PreviewTest
@Preview(name = {kotlin(scene['id'])}, device = {kotlin(device)},
    locale = {kotlin(preview_locale(scene['locale']))}, showSystemUi = {kotlin(scene['system_ui'])},
    showBackground = true, fontScale = {scene['font_scale']}f,
    uiMode = Configuration.UI_MODE_NIGHT_{'YES' if scene['theme'] == 'dark' else 'NO'})
@Composable
fun {scene['method']}() {{
    Box(Modifier.fillMaxSize()) {{
        CaptureScene(CaptureInput({kotlin(scene['id'])}, {kotlin(scene['locale'])},
            {kotlin(scene['theme'] == 'dark')}, {kotlin(scene['mock'])}))
    }}
}}
'''
    (directory / "GeneratedCaptures.kt").write_text(source, encoding="utf-8")


def prepare(args):
    info = inspect_project(args.project, args.module)
    scenes = normalize_request(load_json(args.request))
    adapter = Path(args.adapter).resolve()
    require(adapter.is_file(), "Adapter file does not exist")
    output = Path(args.output).resolve()
    require(not output.exists(), "Output directory already exists; choose a new directory to avoid mixing old PNGs")
    output.mkdir(parents=True)
    workspace = output / "workspace"
    snapshot(info["project"], workspace)
    backend = args.backend
    if backend == "auto":
        require(info["agp"], "Could not determine AGP version; choose --backend legacy or suites after inspecting the build")
        version = tuple(int(x) for x in re.findall(r"\d+", info["agp"])[:2])
        require(version >= (8, 5), "Google screenshot testing requires AGP >=8.5; do not upgrade the original project automatically")
        early_95 = re.fullmatch(r"9\.5\.0-alpha0[12]", info["agp"])
        backend = "suites" if version >= (9, 5) and not early_95 else "legacy"
    task, references = configure_build(workspace, info, backend, args.engine, args.variant)
    module_dir = workspace.joinpath(*info["module"].strip(":").split(":"))
    if any(s["system_ui"] for s in scenes):
        resources = module_dir / "src/main/res/values/code_to_screenshot_system_ui.xml"
        require(not resources.exists(), "Reserved system UI capture resource already exists")
        resources.parent.mkdir(parents=True, exist_ok=True)
        resources.write_text('''<resources>
  <style name="CodeToScreenshotDark" parent="android:style/Theme.Material.NoActionBar">
    <item name="android:statusBarColor">#121212</item>
    <item name="android:navigationBarColor">#121212</item>
    <item name="android:windowLightStatusBar">false</item>
    <item name="android:windowLightNavigationBar">false</item>
  </style>
  <style name="CodeToScreenshotLight" parent="android:style/Theme.Material.Light.NoActionBar">
    <item name="android:statusBarColor">#FAFAFA</item>
    <item name="android:navigationBarColor">#FAFAFA</item>
    <item name="android:windowLightStatusBar">true</item>
    <item name="android:windowLightNavigationBar">true</item>
  </style>
</resources>''', encoding="utf-8")
    generate_previews(module_dir / "src/screenshotTest/kotlin/dev/codetoscreenshot/generated", scenes, adapter)
    if args.sdk_dir:
        (workspace / "local.properties").write_text("sdk.dir=" + Path(args.sdk_dir).resolve().as_posix() + "\n", encoding="utf-8")
    plan = dict(schema_version=1, status="prepared", renderer="google-compose-preview-layoutlib", engine=args.engine,
                backend=backend, source_project=info["project"], workspace=str(workspace), task=task,
                reference_dir=str(references), scenes=scenes, java_home=args.java_home,
                gradle_home=args.gradle_home, user_home=args.user_home, sdk_dir=args.sdk_dir, offline=args.offline,
                adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest())
    save_json(output / "capture-plan.json", plan)
    return output


def png_size(path):
    return png_dimensions(Path(path).read_bytes(), str(path))


def png_dimensions(data, path="native PNG"):
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"Not a PNG: {path}")
    position, dimensions, ended = 8, None, False
    while position + 12 <= len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + length]
        checksum = data[position + 8 + length:position + 12 + length]
        require(len(checksum) == 4 and zlib.crc32(kind + payload) & 0xffffffff == struct.unpack(">I", checksum)[0], f"Damaged PNG chunk: {path}")
        if kind == b"IHDR":
            dimensions = struct.unpack(">II", payload[:8])
        if kind == b"IEND":
            ended = True
            break
        position += length + 12
    require(ended and dimensions is not None, f"Incomplete PNG: {path}")
    return dimensions


def read_native_png(path, java):
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "filesystem"
    # Some managed Windows hosts expose Java-created files differently to Python.
    # Read with the renderer's JDK and transfer the exact bytes over stdout.
    helper = Path(__file__).resolve().with_name("NativePngExport.java")
    process = subprocess.run([java, str(helper), str(path)], capture_output=True, shell=False, timeout=60)
    require(process.returncode == 0 and process.stdout.startswith(b"\x89PNG\r\n\x1a\n"),
            f"Native renderer did not produce a readable PNG: {path}")
    return process.stdout, "jdk-file-stream"


def system_ui_agent(output, java):
    directory = output / "native-system-ui"
    directory.mkdir(exist_ok=True)
    java_bin = Path(java).resolve().parent
    suffix = ".exe" if os.name == "nt" else ""
    source = Path(__file__).with_name("LayoutlibSystemUiAgent.java")
    export = "java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED"
    commands = [
        [str(java_bin / ("javac" + suffix)), "--add-exports", export, "-d", str(directory), str(source)],
    ]
    manifest = directory / "MANIFEST.MF"
    manifest.write_text("Manifest-Version: 1.0\nPremain-Class: LayoutlibSystemUiAgent\nBoot-Class-Path: layoutlib-system-ui.jar\n\n", encoding="utf-8")
    jar = directory / "layoutlib-system-ui.jar"
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        require(result.returncode == 0, "Cannot compile Layoutlib system UI compatibility adapter: " + result.stderr)
    classes = sorted(p.name for p in directory.glob("*.class"))
    result = subprocess.run([str(java_bin / ("jar" + suffix)), "cfm", str(jar), str(manifest), *classes],
                            cwd=directory, capture_output=True, text=True)
    require(result.returncode == 0, "Cannot package Layoutlib system UI adapter: " + result.stderr)
    return jar, export


def render(output):
    output = Path(output).resolve()
    plan = load_json(output / "capture-plan.json")
    workspace = Path(plan["workspace"]).resolve()
    require(workspace == output / "workspace", "Prepared workspace must belong to this capture directory")
    java_home = plan.get("java_home") or os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")) if java_home else shutil.which("java")
    require(java, "JDK not found; set JAVA_HOME or --java-home")
    bars = [s for s in plan["scenes"] if s["system_ui"]]
    if bars:
        require(plan["engine"] == ENGINE, "Native system UI adapter is verified only with engine " + ENGINE)
        jar, export = system_ui_agent(output, java)
        init = output / "system-ui.init.gradle"
        init.write_text("allprojects { tasks.withType(org.gradle.api.tasks.testing.Test).configureEach {\n"
                        + "inputs.file(" + json.dumps(jar.as_posix()) + ")\n"
                        + "jvmArgs " + json.dumps("--add-exports=" + export) + ", "
                        + json.dumps("-javaagent:" + jar.as_posix()) + "\n} }\n", encoding="utf-8")
    command = [java]
    if plan.get("user_home"):
        command += ["-Duser.home=" + plan["user_home"]]
    command += ["-cp", str(workspace / "gradle/wrapper/gradle-wrapper.jar"), "org.gradle.wrapper.GradleWrapperMain",
                "-p", str(workspace), plan["task"], "--console=plain", "--no-daemon", "--stacktrace"]
    if plan["offline"]:
        command += ["--offline"]
    if bars:
        command += ["--init-script", str(init)]
    env = os.environ.copy()
    if java_home:
        env["JAVA_HOME"] = java_home
    if plan.get("gradle_home"):
        env["GRADLE_USER_HOME"] = plan["gradle_home"]
    if plan.get("sdk_dir"):
        env["ANDROID_HOME"] = plan["sdk_dir"]
    env["ANDROID_USER_HOME"] = str(output / ".android")
    env["ANDROID_PREFS_ROOT"] = str(output)
    save_json(output / "invocation.json", {"argv": command, "cwd": str(workspace)})
    started = time.monotonic()
    print(f"Rendering {len(plan['scenes'])} scene(s) with Google Layoutlib; log: {output / 'render.log'}", flush=True)
    with (output / "render.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=workspace, env=env, stdout=log, stderr=subprocess.STDOUT, shell=False)
    report = {"schema_version": 1, "renderer": plan["renderer"], "backend": plan["backend"], "engine": plan["engine"],
              "status": "failed", "duration_seconds": round(time.monotonic() - started, 2), "images": [], "errors": []}
    if result.returncode:
        report["errors"].append(f"Gradle exited {result.returncode}; inspect render.log. No fallback redraw was used.")
    else:
        references = Path(plan["reference_dir"])
        candidates = list(references.rglob("*.png")) if references.exists() else []
        for scene in plan["scenes"]:
            matching = [p for p in candidates if re.search(re.escape(scene["method"]) + r"(?:_|\.|$)", p.name)]
            if len(matching) != 1:
                report["errors"].append(f"{scene['id']}: expected exactly one native PNG, found {len(matching)}")
                continue
            try:
                data, transfer = read_native_png(matching[0], java)
                size = png_dimensions(data, str(matching[0]))
                expected = (scene["resolution"]["width"], scene["resolution"]["height"])
                require(size == expected, f"{scene['id']}: native render is {size}, requested {expected}; PNG was NOT resized or padded")
                target = output / (scene["id"] + ".png")
                target.write_bytes(data)
                report["images"].append({"id": scene["id"], "path": str(target), "width": size[0], "height": size[1],
                                         "sha256": hashlib.sha256(data).hexdigest(), "native_transfer": transfer,
                                         "system_ui_renderer": "layoutlib-native-decorations-alpha16-compat" if scene["system_ui"] else "none",
                                         "settings": {k: v for k, v in scene.items() if k != "method"}})
            except CaptureError as exc:
                report["errors"].append(str(exc))
    report["status"] = "complete" if not report["errors"] and len(report["images"]) == len(plan["scenes"]) else "failed"
    save_json(output / "result.json", report)
    if report["errors"]:
        raise CaptureError("\n".join(report["errors"]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Read project versions and discover preview files")
    inspect.add_argument("--project", required=True)
    inspect.add_argument("--module", default="app")
    for name in ("prepare", "capture"):
        p = sub.add_parser(name, help="Isolate project and generate previews" if name == "prepare" else "Prepare, render, validate and export PNGs")
        p.add_argument("--project", required=True)
        p.add_argument("--module", default="app")
        p.add_argument("--adapter", required=True)
        p.add_argument("--request", required=True)
        p.add_argument("--output", required=True)
        p.add_argument("--variant", default="debug")
        p.add_argument("--backend", choices=("auto", "legacy", "suites"), default="auto")
        p.add_argument("--engine", default=ENGINE)
        p.add_argument("--java-home")
        p.add_argument("--gradle-home")
        p.add_argument("--sdk-dir")
        p.add_argument("--user-home", help="Optional JVM user.home for restricted runners; not needed on normal desktops")
        p.add_argument("--offline", action="store_true")
    p = sub.add_parser("render", help="Render an already prepared isolated workspace")
    p.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            print(json.dumps(inspect_project(args.project, args.module), ensure_ascii=False, indent=2))
        elif args.command == "render":
            render(args.run_dir)
        else:
            output = prepare(args)
            if args.command == "capture":
                render(output)
            else:
                print(json.dumps({"prepared": str(output), "plan": str(output / "capture-plan.json")}, indent=2))
        return 0
    except (CaptureError, OSError, ValueError) as exc:
        print(f"code-to-screenshot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
