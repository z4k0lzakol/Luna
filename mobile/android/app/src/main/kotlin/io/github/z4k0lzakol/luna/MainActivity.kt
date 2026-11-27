package io.github.z4k0lzakol.luna

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/** Luna otwiera linki z innych aplikacji (Luna jako przeglądarka): adres trafia do Fluttera kanałem „luna/links”.
 *  Kanał „luna/update”: pobrany Luna-Android.apk trafia do systemowego okna instalacji (lib/update.dart). */
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
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "luna/update").setMethodCallHandler { call, result ->
            if (call.method != "install") return@setMethodCallHandler result.notImplemented()
            try {
                result.success(installApk(File(call.argument<String>("path")!!)))
            } catch (e: Exception) {
                result.error("install", e.message, null)
            }
        }
    }

    /** "settings" – Android wymaga zgody na instalowanie aplikacji z Luny (otwiera jej ustawienie), "ok" – okno instalacji. */
    private fun installApk(apk: File): String {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            return "settings"
        }
        val uri = FileProvider.getUriForFile(this, "$packageName.aktualizacje", apk)
        startActivity(Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        })
        return "ok"
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
