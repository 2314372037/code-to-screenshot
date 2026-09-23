# Code to Screenshot

An AI coding agent skill that turns real Android Jetpack Compose code into PNG screenshots using Google's Layoutlib renderer. No emulator, manual capture, or Android Studio required.

Choose mock content, language, light or dark theme, phone or tablet layout, system bars, and exact pixel dimensions in plain language. The skill renders your actual UI in an isolated project copy, leaving the original source unchanged.

## Install

### Using npx skills

```bash
npx skills add 2314372037/code-to-screenshot
```

Add `-g` to install globally.

### Manual install

Clone into your agent's skills directory. For Claude Code:

```bash
git clone https://github.com/2314372037/code-to-screenshot.git ~/.claude/skills/code-to-screenshot
```

### Requirements

- Python 3.11+ and a JDK / Android SDK compatible with your project.
- An Android Jetpack Compose project.
- Internet access to download build dependencies on the first run.
- Enough disk space for an isolated project copy and build output. The first capture requires a fresh build and takes longer.

## Usage

1. Open your Compose project in your coding agent.
2. Ask for a screenshot, naming the screen and any settings you want:

   ```text
   Use code-to-screenshot to capture my weather screen in Chinese.
   Show Shanghai, light rain, 18°C, and 84% humidity.
   Use a dark phone layout with system bars at 1080 × 2400 pixels.
   ```

3. The agent inspects the project, connects mock data to your screen, and renders the PNGs. You receive screenshots and a capture summary; the output folder also includes logs and the isolated workspace.

You can request multiple variations at once:

```text
Use code-to-screenshot to capture my dashboard in English,
with light and dark themes for both phone and tablet layouts.
Use realistic sample data and hide the system bars.
```

## From Code to Store Screenshots

Pair this skill with [app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots) to take your Compose app from code to finished store marketing screenshots in one agent workflow:

**Compose code → native PNGs → marketing layouts → store-ready PNG bundle**

Install the companion skill:

```bash
npx skills add ParthJadhav/app-store-screenshots
```

Then give your agent one request:

```text
Use code-to-screenshot and app-store-screenshots together to create
Google Play screenshots for my Android app from start to finish.

Capture the key Compose screens with realistic mock data using
code-to-screenshot. Pass the generated PNGs directly to
app-store-screenshots, then create 5 marketing slides with device
frames, concise feature headlines, and a clean, modern style.
Use English and export the final Google Play PNG bundle.

Handle capture, asset handoff, layout, and export automatically.
Check the rendered images and deliver the final files.
```

The agent coordinates both skills; automated export requires an agent with browser control and the companion editor's runtime dependencies. The workflow ends with files ready to upload, rather than publishing to a store account. For Apple App Store assets, provide genuine iOS captures separately; this skill captures Android Compose only.

## Scope

Android Jetpack Compose only. This skill produces UI screenshots, without device frames or store marketing layouts. SwiftUI is not supported.

Layoutlib is a preview environment, so screens that depend on live services or unsupported native APIs may need mock dependencies. The Windows / JDK 21 / AGP 9.4 route has been verified with real renders; AGP 9.5 native suite configuration is available but has not been fully tested.

## Examples & Reference

- [Verified screenshots](examples/verified)
- [Runnable Compose demo](examples/compose-demo)
- [Capture settings and mock data](references/request.md)
- [Renderer setup and limitations](references/layoutlib.md)
