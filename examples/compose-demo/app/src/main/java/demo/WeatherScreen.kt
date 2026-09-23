package demo

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun WeatherScreen(
    city: String,
    temperature: Int,
    dark: Boolean,
    weather: String = "rain",
    humidity: Int = 84
) {
    MaterialTheme(colorScheme = if (dark) darkColorScheme() else lightColorScheme()) {
        Surface(Modifier.fillMaxSize()) {
            BoxWithConstraints(Modifier.fillMaxSize().padding(24.dp)) {
                val tablet = maxWidth >= 600.dp
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(stringResource(R.string.weather_title), style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary)
                    Text(city, style = MaterialTheme.typography.headlineLarge)
                    Text("${temperature}°", fontSize = if (tablet) 104.sp else 64.sp, fontWeight = FontWeight.Light)
                    Text(stringResource(when(weather) {
                        "sunny" -> R.string.sunny
                        "cloudy" -> R.string.cloudy
                        else -> R.string.rain
                    }), style = MaterialTheme.typography.headlineSmall)
                    if (tablet) {
                        Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                            ForecastCard(temperature, Modifier.weight(1f))
                            HumidityCard(humidity, Modifier.weight(1f))
                        }
                    } else {
                        ForecastCard(temperature, Modifier.fillMaxWidth())
                        HumidityCard(humidity, Modifier.fillMaxWidth())
                    }
                    Button(onClick = {}) { Text(stringResource(R.string.details)) }
                }
            }
        }
    }
}

@Composable
private fun ForecastCard(temperature: Int, modifier: Modifier) {
    Card(modifier, shape = RoundedCornerShape(24.dp)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text(stringResource(R.string.hourly), style = MaterialTheme.typography.titleMedium)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                for (index in 0..3) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("${9 + index}:00", style = MaterialTheme.typography.labelMedium)
                        Text("${temperature + index}°", style = MaterialTheme.typography.titleLarge)
                    }
                }
            }
        }
    }
}

@Composable
private fun HumidityCard(humidity: Int, modifier: Modifier) {
    Card(modifier, shape = RoundedCornerShape(24.dp)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.humidity), style = MaterialTheme.typography.titleMedium)
            Text("${humidity}%", style = MaterialTheme.typography.displaySmall)
        }
    }
}
