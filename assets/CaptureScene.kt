// Adapt the import and content call to the actual project. Keep the app's real UI.
package screenshot.scenes

import androidx.compose.runtime.Composable
import dev.codetoscreenshot.generated.CaptureInput
import demo.WeatherScreen

@Composable
fun CaptureScene(input: CaptureInput) {
    WeatherScreen(
        city = input.text("city", "Shanghai"),
        temperature = input.number("temperature", 18.0).toInt(),
        dark = input.dark,
        weather = input.text("weather", "rain"),
        humidity = input.number("humidity", 84.0).toInt()
    )
}
