# 真实渲染验证

使用本项目 Compose 示例、assets/CaptureScene.kt 和 request.json，通过 Google Compose Preview Screenshot Testing alpha16 / Layoutlib 实际生成。

环境：Windows、JDK 21、AGP 9.4、Gradle 9.6、Android SDK 37.1。三张 PNG 均验证完整性、原生像素尺寸和 SHA-256；深色手机/平板已目视确认原生状态栏和导航栏。系统栏使用项目附带的 alpha16 兼容适配。

- shanghai-rain-dark.png：720×1280，中文、上海、小雨18度、湿度84%、深色、系统栏。
- london-sun-light.png：720×1280，英文、London、晴23度、湿度52%、浅色、无系统栏。
- tablet-dark.png：1600×2560，中文、北京、多云12度、湿度67%、深色、系统栏、平板双列布局。

result.json 保留每张原始图片的哈希与设置，路径改为相对此目录。图片未缩放、未重绘。AGP 9.5 原生 test suite 配置尚未进行完整渲染验证。
