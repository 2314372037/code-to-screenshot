# Official renderer and compatibility

This skill invokes Google's Compose Preview Screenshot Testing engine, which uses Layoutlib on the host. It does not require a device, emulator, Android Studio UI, or user-supplied screenshot.

Authoritative references (checked 2026-09-22):

- [Standalone screenshot plugin](https://developer.android.com/studio/preview/compose-screenshot-testing)
- [Native AGP screenshot test suites](https://developer.android.com/studio/preview/compose-screenshot-testing-with-testsuites)
- [Preview configuration and limitations](https://developer.android.com/develop/ui/compose/tooling/previews)

The engine is experimental. Current default is `0.0.1-alpha16`.

## Backend selection

- AGP 8.5–9.4: standalone `com.android.compose.screenshot` plugin and `update<Variant>ScreenshotTest`.
- AGP 9.5.0-alpha03 and later: native screenshot suite and `updateScreenshotTestDefault<Variant>TestSuite`.
- `--backend auto` infers AGP from the standard version catalog or plugin declaration. Use explicit `--backend legacy|suites` for convention-plugin builds after reading their configuration. AGP 9.5 alpha01/alpha02 select legacy.
- Current automatic preparation supports Kotlin Gradle DSL Android application/library modules. Groovy DSL, existing native screenshot suites, non-Android KMP targets, composite builds outside the project root, and symlinked source trees require an explicit isolated capture harness; do not claim they were rendered automatically.

Do not upgrade the user's AGP, Kotlin, SDK, or dependency versions just to fit the tool. Pick a compatible engine or adapt the capture-only workspace. System UI and font rendering are provided by Layoutlib, so they may differ from a particular vendor's phone.

## Environment

## Native system UI compatibility

Engine alpha16's `RenderEnvironmentBootstrapper` unconditionally calls `disableDecorations()` and selects `SHRINK`, so `@Preview(showSystemUi=true)` alone does not produce bars in its standalone screenshots. This was confirmed in a real render and in the bundled renderer bytecode.

For scenes requesting bars, the runner compiles the small `LayoutlibSystemUiAgent.java` compatibility adapter. In that isolated test JVM only, it enables `RenderTask.setDecorations(true)` and `NORMAL` rendering for the generated, explicitly marked preview. It selects a generated Android framework light/dark no-action-bar theme. Layoutlib itself draws the status icons and navigation bar; the runner does not paint overlays or modify the downloaded engine/cache. This is a version-pinned compatibility extension around Google's renderer, not an upstream Google feature. JDK `javac` and `jar` are required. Other engine versions with system UI fail explicitly until validated.

Bars use deterministic preview time/icons and neutral light/dark colors, not device OEM branding or the application's Activity window styling. Pixel resolution includes both bars. Native suites configuration is provided but has not yet been end-to-end validated; the verified backend is the standalone plugin on Windows/JDK 21.

On hosts where native Java file reads and Python file reads differ, `NativePngExport.java` streams the exact original PNG bytes through the rendering JDK. It does not decode, re-encode, resize, or draw an image. The manifest records this transfer mode.

## Toolchain

Python 3.11+, a working project Gradle wrapper, compatible JDK, Android SDK/platform, and access to Google Maven/Maven Central for the first render. The demo uses AGP 9.4, Kotlin 2.4.20, Android SDK 37.1, and JDK 21. Other projects retain their own toolchain.

Use `--java-home`, `--sdk-dir`, and `--gradle-home` when not already configured. `--user-home` is only for restricted execution environments with a broken JVM user-home location. No machine-specific paths are embedded in the skill. `--offline` works only after all dependencies have been downloaded.

## Isolation and outputs

`prepare` copies source into `<output>/workspace`, excluding build/cache directories and existing screenshot-test source sets. It modifies only that copy. Keep the generated workspace and `render.log` for diagnosis. `render --run-dir <output>` retries that same workspace. The output directory must be new on `capture`/`prepare`; this prevents accidental export of stale PNGs.

The resulting `result.json` contains exact dimensions, hashes, effective settings and mock content. Only `status: complete` with the requested number of images is success. A failed render must never be replaced by an approximation image. Native PNG size mismatches fail instead of silently cropping or resampling.

## Troubleshooting

Read the first relevant error in `render.log`, not only the final Gradle summary. Check toolchain compatibility, offline dependency availability, mock dependencies, and native rendering errors. Preview cannot perform arbitrary network/file operations and some Android APIs are not implemented. Freeze unavailable services at the data boundary, preserving the actual composable.

If a required GPU or platform API cannot render in Layoutlib, report that specific limitation. This version does not fall back to simulator screenshots, hand drawing, or marketing artwork. Fix the isolated adapter/configuration and rerun `render`; do not modify the original application without a separate need and authorization.
