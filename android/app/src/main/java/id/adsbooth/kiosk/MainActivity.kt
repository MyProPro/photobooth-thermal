package id.adsbooth.kiosk

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.app.ActivityCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {

    private lateinit var web: WebView
    private lateinit var status: TextView
    private val kioskUrl = "http://127.0.0.1:5000/?kiosk=1"
    private val probeUrl = "http://127.0.0.1:5000/api/config"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        web = findViewById(R.id.web)
        status = findViewById(R.id.status)

        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.mediaPlaybackRequiresUserGesture = false
        web.webViewClient = WebViewClient()
        web.addJavascriptInterface(AndroidPrintInterface(this), "AndroidUsbPrinter")
        web.addJavascriptInterface(PhotoPrintBridge(this), "AndroidPhotoPrinter") 
        UsbPrinterBridge.init(this)
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread { request.grant(request.resources) }
            }
        }

        // Tombol Back: kembali di dalam WebView (mis. dari Studio ke kiosk),
        // baru keluar aplikasi kalau sudah di halaman paling awal.
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) {
                    web.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), 1)
        }

        startPythonServer()
        waitThenLoad()
    }

    override fun onResume() {
        super.onResume()
        // Cek dan minta izin USB otomatis setiap kali kembali ke aplikasi (mis. setelah aktifkan OTG di Pengaturan)
        try {
            if (!UsbPrinterBridge.hasPermission()) {
                UsbPrinterBridge.requestPermission(null)
            }
        } catch (_: Exception) {}
    }

    private fun startPythonServer() {
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        val py = Python.getInstance()
        val dataDir = filesDir.absolutePath
        thread(name = "adsbooth-server", isDaemon = true) {
            try {
                py.getModule("android_main").callAttr("start_server", dataDir)
            } catch (e: Throwable) {
                runOnUiThread { status.text = "Python error: " + e.message }
            }
        }
    }

    private fun waitThenLoad() {
        thread(isDaemon = true) {
            val deadline = System.currentTimeMillis() + 90000
            while (System.currentTimeMillis() < deadline) {
                try {
                    val c = URL(probeUrl).openConnection() as HttpURLConnection
                    c.connectTimeout = 1000
                    c.readTimeout = 1000
                    val code = c.responseCode
                    c.disconnect()
                    if (code in 200..499) {
                        runOnUiThread {
                            status.visibility = View.GONE
                            web.loadUrl(kioskUrl)
                            // Minta izin USB secara otomatis jika printer terpasang
                            try { UsbPrinterBridge.requestPermission(null) } catch (_: Exception) {}
                        }
                        return@thread
                    }
                } catch (_: Exception) {
                }
                Thread.sleep(500)
            }
            runOnUiThread { status.text = "Server gagal start (cek Logcat)" }
        }
    }

    override fun onDestroy() {
        UsbPrinterBridge.destroy(this)
        web.destroy()
        super.onDestroy()
    }
}
