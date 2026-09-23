# code-to-screenshot

独立的 Codex skill：**真实 Android Compose 代码 → Google Layoutlib → PNG**。不需要手动截图、模拟器或打开 Android Studio；不制作商店宣传图。**仅面向 Android Jetpack Compose，暂不支持 SwiftUI 或其它平台。**

支持自然语言指定 mock 数据、语言、light/dark、手机/平板、系统栏开关和像素分辨率。Skill 负责理解需求、连接项目的数据模型；Python 工具负责隔离项目、生成预览、执行官方截图任务和检查输出。

## 使用

将本目录作为个人 skill 安装或在任务中直接引用 `SKILL.md`，然后描述目标，例如：

> 用 $code-to-screenshot 把天气页生成中文深色手机截图，上海小雨 18 度、湿度 84%，显示系统栏，1080×2400。

首次运行需要 Python 3.11+、与项目匹配的 JDK/Android SDK，以及下载官方构建依赖的网络。**原项目源码不会被修改**，但工具会把整个项目复制到隔离工作区（见下文「隔离方式与范围」）。

命令行调用（adapter 和 request 由 agent 按项目生成）：

```text
python scripts/capture.py inspect --project /path/to/project --module app
python scripts/capture.py capture --project /path/to/project --module app --adapter /path/to/CaptureScene.kt --request /path/to/request.json --output /path/to/new-output
```

输出为 PNG、`result.json`、`capture-plan.json`、渲染日志和可检查的隔离工作区。分辨率是 PNG 原生像素，不是缩放后的尺寸。

- [完整参数与 mock 接口](references/request.md)
- [官方渲染路线、环境和限制](references/layoutlib.md)
- [可运行的 Compose 示例](examples/compose-demo)
- [多场景配置示例](assets/request.example.json)

## 隔离方式与范围

- **会复制整个项目**：`prepare` 会把项目完整快照到 `<output>/workspace`（排除 `build/`、`.git/`、`.gradle/`、`.idea/` 等），只在**副本**里注入官方截图插件、生成预览并构建。原项目源码在任何情况下都不会被修改，但需要预留与项目等量的磁盘空间，且首轮需要重新全量编译（这是首次较慢的主要原因）。
- **仅支持 Android Jetpack Compose**：渲染依赖 Google Layoutlib 预览引擎，**暂不支持 SwiftUI**。
- **只产出原生 UI 截图**：不添加设备边框、宣传文案或商店尺寸，也不回退到模拟器截图或手绘图像。
- **Layoutlib 限制**：它是本地预览环境，不是完整 Android 运行时。系统栏由 Layoutlib 原生绘制（依赖版本限定的兼容适配）；涉及实时服务、特定 GPU API 或畸形字节码依赖的页面可能无法渲染，需要把这些依赖隔离出截图运行时。
- **后端**：已验证 Windows / JDK 21 / AGP 9.4 的官方独立插件路线；AGP 9.5 原生 suite 仅提供配置，尚未完整实测。

## 开发验证

```text
python -m unittest discover -s tests -v
```

真实渲染的验证结果见 [examples/verified](examples/verified)。已验证 Windows、JDK 21、AGP 9.4 的官方独立插件路线；AGP 9.5 原生 suite 已提供配置，尚未完整实测。
