package io.github.z4k0lzakol.luna

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/** Luna otwiera linki z innych aplikacji (Luna jako przeglądarka): adres trafia do Fluttera kanałem „luna/links”. */
class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var pending: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        pending = linkOf(intent)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "luna/links").also {
            it.setMethodCallHandler { call, result ->
                if (call.method == "initialLink") {
                    result.success(pending)
                    pending = null
                } else {
                    result.notImplemented()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        linkOf(intent)?.let { channel?.invokeMethod("openLink", it) }
    }

    private fun linkOf(i: Intent?): String? {
        if (i?.action != Intent.ACTION_VIEW) return null
        val s = i.dataString ?: return null
        return if (s.startsWith("http://") || s.startsWith("https://")) s else null
    }
}
