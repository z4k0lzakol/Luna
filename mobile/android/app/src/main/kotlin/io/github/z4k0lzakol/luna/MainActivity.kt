package io.github.z4k0lzakol.luna

import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.provider.Settings
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import java.io.File
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/** Luna otwiera linki z innych aplikacji (Luna jako przeglądarka): adres trafia do Fluttera kanałem „luna/links”.
 *  Kanał „luna/update”: pobrany Luna-Android.apk trafia do systemowego okna instalacji (lib/update.dart).
 *  Kanał „luna/link”: połączone urządzenia (lib/link/) – wybór plików, zapis do Pobrane/Luna, „Udostępnij → Luna”,
 *  zgoda Wi-Fi na odbieranie ogłoszeń w sieci (multicast). */
class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var linkChannel: MethodChannel? = null
    private var pending: String? = null
    private var pendingShared: List<String>? = null
    private var sharedAsked = false
    private var pickResult: MethodChannel.Result? = null
    private var multicast: WifiManager.MulticastLock? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        pending = linkOf(intent)
        val start = intent
        if (start?.action == Intent.ACTION_SEND || start?.action == Intent.ACTION_SEND_MULTIPLE) {
            Thread {   // kopiowanie dużych plików poza wątkiem interfejsu
                val files = sharedOf(start)
                runOnUiThread {
                    if (sharedAsked && !files.isNullOrEmpty()) linkChannel?.invokeMethod("sharedFiles", files) else pendingShared = files
                }
            }.start()
        }
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
            if (call.method == "isWifi") return@setMethodCallHandler result.success(onWifi())
            if (call.method != "install") return@setMethodCallHandler result.notImplemented()
            try {
                result.success(installApk(File(call.argument<String>("path")!!)))
            } catch (e: Exception) {
                result.error("install", e.message, null)
            }
        }
        linkChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "luna/link").also {
            it.setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "multicast" -> { setMulticast(call.argument<Boolean>("on") == true); result.success(true) }
                        "pickFiles" -> pickFiles(result)
                        "saveToDownloads" -> result.success(saveToDownloads(File(call.argument<String>("path")!!),
                            call.argument<String>("name")!!))
                        "openSaved" -> { openSaved(call.argument<String>("uri")!!); result.success(true) }
                        "initialShared" -> { sharedAsked = true; result.success(pendingShared); pendingShared = null }
                        else -> result.notImplemented()
                    }
                } catch (e: Exception) {
                    result.error("link", e.message, null)
                }
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

    /** Sieć bez limitu danych (Wi-Fi, Ethernet) – aktualizacje pobierane w tle tylko wtedy (domyślnie). */
    private fun onWifi(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) ||
            caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET)
    }

    // --- połączone urządzenia ---
    private fun setMulticast(on: Boolean) {
        if (on) {
            if (multicast == null) {
                val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                multicast = wifi.createMulticastLock("luna-link").apply { setReferenceCounted(false) }
            }
            multicast?.acquire()
        } else {
            multicast?.let { if (it.isHeld) it.release() }
        }
    }

    private fun pickFiles(result: MethodChannel.Result) {
        pickResult?.success(null)
        pickResult = result
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
        }, PICK)
    }

    @Deprecated("FlutterActivity nie ma jeszcze Activity Result API")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != PICK) return
        val r = pickResult ?: return
        pickResult = null
        if (resultCode != Activity.RESULT_OK || data == null) return r.success(emptyList<String>())
        val uris = mutableListOf<Uri>()
        data.clipData?.let { c -> for (i in 0 until c.itemCount) uris.add(c.getItemAt(i).uri) }
        if (uris.isEmpty()) data.data?.let { uris.add(it) }
        Thread {
            val paths = try { copyToCache(uris) } catch (e: Exception) { emptyList() }
            runOnUiThread { r.success(paths) }
        }.start()
    }

    /** Kopia wybranych / udostępnionych plików do pamięci podręcznej Luny – pod oryginalną nazwą, bez zmian w treści. */
    private fun copyToCache(uris: List<Uri>): List<String> {
        val dir = File(cacheDir, "wyslij/${System.currentTimeMillis()}").apply { mkdirs() }
        return uris.mapNotNull { uri ->
            val name = displayName(uri)
            val dest = File(dir, name)
            contentResolver.openInputStream(uri)?.use { input -> dest.outputStream().use { input.copyTo(it, 1 shl 20) } } ?: return@mapNotNull null
            dest.absolutePath
        }
    }

    private fun displayName(uri: Uri): String {
        var name: String? = null
        try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) name = c.getString(0)
            }
        } catch (_: Exception) {}
        val n = (name ?: uri.lastPathSegment ?: "plik").substringAfterLast('/').replace(Regex("[\\\\:*?\"<>|]"), "_").trim()
        return n.ifEmpty { "plik" }
    }

    /** Odebrany plik → Pobrane/Luna (MediaStore, Android 10+) albo folder Pobrane aplikacji (starsze). Zwraca adres pliku. */
    private fun saveToDownloads(src: File, name: String): String {
        val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase())
            ?: "application/octet-stream"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                put(MediaStore.MediaColumns.MIME_TYPE, mime)
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Luna")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            }
            val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("nie udało się zapisać w Pobranych")
            contentResolver.openOutputStream(uri)?.use { out -> src.inputStream().use { it.copyTo(out, 1 shl 20) } }
            contentResolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
            src.delete()
            return uri.toString()
        }
        val dir = File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "Luna").apply { mkdirs() }
        var dest = File(dir, name)
        var i = 2
        while (dest.exists()) {
            dest = File(dir, name.substringBeforeLast('.') + " ($i)" + (if ('.' in name) "." + name.substringAfterLast('.') else ""))
            i++
        }
        src.copyTo(dest)
        src.delete()
        return Uri.fromFile(dest).toString()
    }

    private fun openSaved(s: String) {
        var uri = Uri.parse(s)
        if (uri.scheme == "file") uri = FileProvider.getUriForFile(this, "$packageName.aktualizacje", File(uri.path!!))
        startActivity(Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, contentResolver.getType(uri) ?: "*/*")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        })
    }

    /** „Udostępnij → Luna” z galerii albo menedżera plików: pliki do wysłania na połączone urządzenie. */
    private fun sharedOf(i: Intent?): List<String>? {
        val uris = when (i?.action) {
            Intent.ACTION_SEND -> listOfNotNull(streamOf(i))
            Intent.ACTION_SEND_MULTIPLE -> streamsOf(i)
            else -> return null
        }
        if (uris.isEmpty()) return null
        return try { copyToCache(uris) } catch (e: Exception) { null }
    }

    @Suppress("DEPRECATION")
    private fun streamOf(i: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java) else i.getParcelableExtra(Intent.EXTRA_STREAM)

    @Suppress("DEPRECATION")
    private fun streamsOf(i: Intent): List<Uri> =
        (if (Build.VERSION.SDK_INT >= 33) i.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else i.getParcelableArrayListExtra(Intent.EXTRA_STREAM)) ?: emptyList()

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        linkOf(intent)?.let { channel?.invokeMethod("openLink", it) }
        if (intent.action == Intent.ACTION_SEND || intent.action == Intent.ACTION_SEND_MULTIPLE) {
            Thread {
                val files = sharedOf(intent)
                if (!files.isNullOrEmpty()) runOnUiThread { linkChannel?.invokeMethod("sharedFiles", files) }
            }.start()
        }
    }

    private fun linkOf(i: Intent?): String? {
        if (i?.action != Intent.ACTION_VIEW) return null
        val s = i.dataString ?: return null
        return if (s.startsWith("http://") || s.startsWith("https://")) s else null
    }

    companion object {
        private const val PICK = 4711
    }
}
