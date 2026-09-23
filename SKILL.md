---
name: code-to-screenshot
description: Render real Android Jetpack Compose code to native PNG screenshots using Google's host-side Layoutlib screenshot engine. Use when a user wants screenshots directly from a Compose project, with chosen mock content, locale, light/dark theme, phone/tablet layout, system bars, and exact pixel resolution, without manually capturing a device. This skill produces plain UI screenshots, not App Store/Google Play marketing layouts, SwiftUI renders, or approximate redraws.
---

# Code to Screenshot

Deliver native PNGs rendered from the project's actual Compose UI. Use the bundled runner to create an isolated capture workspace, generate Google screenshot previews, render with Layoutlib, and verify exact dimensions. Read [request and adapter contract](references/request.md) before preparing a capture. Read [renderer compatibility](references/layoutlib.md) when configuring or troubleshooting a project.

## Capture the user's intent

Extract the target screen and requested mock content, language, theme, device category, system-UI visibility, and resolution from the request and project context. Support natural-language descriptions and choices. If relevant settings remain ambiguous, ask one compact question with choices rather than walking through a technical form. Use explicit user choices first. Otherwise infer sensible values from the existing preview and state the defaults in the result; do not repeatedly ask for optional settings.

Example: “把天气页生成中文深色手机截图，上海小雨 18 度，显示状态栏和导航栏，1080×2400。” A complete request requires no further questions. Phone/tablet means layout space, not a decorative device frame.

## Inspect and adapt

1. Run `python scripts/capture.py inspect --project <path> --module <module>` and read the selected screen, theme, UI state models and previews.
2. Generate a request JSON using the contract. Author realistic, consistent mock content; keep dates and random data deterministic. Create a small Kotlin adapter with `@Composable fun CaptureScene(input: CaptureInput)` calling the actual screen and app theme. Start from [the adapter example](assets/CaptureScene.kt) but replace its demo import and model wiring. Map every requested mock field to an actual visible state. Apply `input.dark` to the app theme, not just a background rectangle.
3. Prefer existing stateless screen functions or previews. Supply CompositionLocals and mock data providers as needed. If a screen starts a ViewModel, network or database, isolate that dependency in the capture adapter/workspace. Preserve the real UI code. Do not replace the screen with hand-drawn HTML/Skia/PIL or generated imagery.

## Render

Run the bundled CLI with absolute paths when the working directory differs from the skill:

```text
python scripts/capture.py capture --project <android-project> --module app --adapter <CaptureScene.kt> --request <request.json> --output <new-output-directory>
```

The runner snapshots the project and edits only `<output>/workspace`. Never patch the source application just to obtain a screenshot. Toolchain options: `--java-home`, `--sdk-dir`, `--gradle-home`, and `--offline` after dependencies are cached. Use `prepare` instead of `capture` if the isolated build needs review or adaptation, then `render --run-dir <output>`.

The first release uses Google's standalone screenshot plugin for AGP 8.5–9.4 and supports configuring native test suites for AGP 9.5.0-alpha03+. Both routes are experimental; choose a compatible route after inspecting the actual build. Do not silently upgrade the application toolchain. Do not claim a backend/platform is tested unless an actual native PNG was generated on it.

## Verify and deliver

Require `result.json` to report `complete` with one PNG per requested scene. Inspect representative PNGs visually: correct screen, visible mock values, theme, language, phone/tablet layout, system bars and no blank/error panels or clipped important content. The runner verifies PNG integrity and exact pixel dimensions; it never rescales or pads a wrong-sized capture.

If native rendering fails, inspect `render.log`, fix the isolated adapter or environment, and retry. Report unsupported native APIs or unavailable dependencies precisely. Never present an approximate redraw as a successful native render.

Return image previews and links to the exported PNGs with a concise settings summary. Include the effective capture request/result manifest so a separate professional screenshot-design skill can consume the assets. Do not add device frames, marketing copy, store-specific sizing, store metadata, or uploads. SwiftUI is outside this version's scope.
