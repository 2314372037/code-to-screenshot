# Capture request and adapter contract

The user describes the desired image in natural language, or chooses options in one compact question. The agent produces a JSON request and a small Kotlin adapter; the user does not need to write either file.

## Supported controls

| Field | Meaning / default |
| --- | --- |
| `id` | Unique lowercase output filename, without `.png` |
| `locale` | BCP-47 locale, e.g. `zh-CN`, `en-US`, `zh-Hant-TW`; default `en-US` |
| `theme` | `light` or `dark`; default `light` |
| `device` | `phone` (<600dp shortest edge) or `tablet` (>=600dp); default phone |
| `resolution` | Exact PNG pixels, `{"width":1080,"height":2400}`; phone default 1080×2400, tablet 1600×2560 |
| `dpi` | Optional density; normally calculated to give a phone 360dp or tablet 800dp shortest edge |
| `system_ui` | One boolean for both native status and navigation bars; default false |
| `mock` | Arbitrary JSON object: weather, dates, items, user names, localized copy, etc. |
| `font_scale` | Optional 0.5–2.0, default 1.0 |

Top level: `schema_version: 1`, optional `defaults`, and `scenes` (1–24 items). Defaults merge shallowly; per-scene `mock` and `resolution` replace the entire corresponding default. Pixel dimensions are never silently rescaled or padded. Landscape is chosen by making width larger than height. Device category changes dp space, not decorative phone/tablet frames.

See [request.example.json](../assets/request.example.json). Pixel size includes the native bars when `system_ui` is true. This release does not independently toggle individual bars or emulate specific OEM navigation styles.

## Kotlin adapter

The adapter must declare a package and `@Composable fun CaptureScene(input: CaptureInput)`. Import `dev.codetoscreenshot.generated.CaptureInput`; the runner generates this class in the isolated screenshot source set.

`CaptureInput` exposes `id`, `locale`, `dark`, `mock: Map<String, Any?>`, plus `text(key, fallback)`, `number(key, fallback)`, and `flag(key, fallback)`. Nested mock objects are maps and arrays are lists. Prefer small typed fixture builders in the adapter for complex model constructors.

Call the real application's theme with `darkTheme = input.dark` (or its equivalent), then the real screen with models built from `input.mock`. Resource locale is set by Layoutlib. Mocked text should be authored in the chosen language. Changing `locale` does not translate hardcoded strings or create missing resource translations.

Reuse UI state models and stateless screen entrypoints. Provide mock dependencies/CompositionLocals where necessary. Do not start real authentication, network requests, databases, location requests, billing, or model downloads. Do not redraw the screen using HTML, PIL, Skia primitives, or image generation. A composable tightly coupled to its ViewModel may need a stateless entrypoint; make any necessary adaptation only in the isolated workspace, document it, and preserve the screen's actual layout.

Mock scene data must visibly affect the screenshot. Do not silently ignore requested fields. For static capture, inject a deterministic state; do not promise to advance arbitrary animations to a requested frame. Layoutlib cannot replace a full Android runtime for every platform service or GPU effect.
