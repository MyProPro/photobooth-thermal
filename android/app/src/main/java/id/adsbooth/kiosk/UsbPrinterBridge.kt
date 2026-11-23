package id.adsbooth.kiosk

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Build
import android.util.Base64
import android.util.Log
import android.webkit.JavascriptInterface
import org.json.JSONObject

object UsbPrinterBridge {
    private const val TAG = "UsbPrinterBridge"
    private const val ACTION_USB_PERMISSION = "id.adsbooth.kiosk.USB_PERMISSION"

    private var activityRef: Activity? = null
    private var usbManager: UsbManager? = null
    private var permissionCallback: ((Boolean) -> Unit)? = null
    private var lastStatusMessage = "Belum diinisialisasi"

    private val usbReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val action = intent?.action ?: return
            if (ACTION_USB_PERMISSION == action) {
                synchronized(this) {
                    val device: UsbDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
                    }
                    val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
                    Log.i(TAG, "USB permission result for ${device?.deviceName}: granted=$granted")
                    lastStatusMessage = if (granted) "Izin USB diberikan" else "Izin USB ditolak oleh pengguna"
                    permissionCallback?.invoke(granted)
                    permissionCallback = null
                }
            }
        }
    }

    @JvmStatic
    fun init(activity: Activity) {
        this.activityRef = activity
        this.usbManager = activity.getSystemService(Context.USB_SERVICE) as? UsbManager
        val filter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            activity.registerReceiver(usbReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            activity.registerReceiver(usbReceiver, filter)
        }
        lastStatusMessage = "Siap mendeteksi printer USB"
        Log.i(TAG, "UsbPrinterBridge diinisialisasi")
    }

    @JvmStatic
    fun destroy(activity: Activity) {
        try {
            activity.unregisterReceiver(usbReceiver)
        } catch (_: Exception) {}
        if (activityRef == activity) {
            activityRef = null
            usbManager = null
        }
    }

    /**
     * Cari printer USB yang terhubung.
     * Prioritas:
     * 1. Perangkat dengan Interface USB Class 7 (Printer)
     * 2. Vendor ID Epson (0x04b8)
     * 3. Perangkat USB apapun yang punya Endpoint BULK OUT (jika hanya ada 1 perangkat USB OTG)
     */
    @JvmStatic
    fun findPrinterDevice(): UsbDevice? {
        val manager = usbManager ?: return null
        val deviceList = manager.deviceList
        if (deviceList.isEmpty()) {
            lastStatusMessage = "Tidak ada perangkat USB terdeteksi. Pastikan kabel OTG tercolok dan opsi 'Koneksi OTG' di Pengaturan Android sudah aktif."
            return null
        }

        // Cek 1: Interface Class 7 (Printer standard)
        for (dev in deviceList.values) {
            for (i in 0 until dev.interfaceCount) {
                val iface = dev.getInterface(i)
                if (iface.interfaceClass == UsbConstants.USB_CLASS_PRINTER) {
                    lastStatusMessage = "Printer terdeteksi: ${dev.productName ?: dev.deviceName} (Class 7)"
                    return dev
                }
            }
        }

        // Cek 2: Vendor Epson (0x04b8)
        for (dev in deviceList.values) {
            if (dev.vendorId == 0x04b8) {
                lastStatusMessage = "Printer Epson terdeteksi: ${dev.productName ?: dev.deviceName} (VID 0x04b8)"
                return dev
            }
        }

        // Cek 3: Perangkat dengan BULK OUT endpoint
        for (dev in deviceList.values) {
            for (i in 0 until dev.interfaceCount) {
                val iface = dev.getInterface(i)
                for (j in 0 until iface.endpointCount) {
                    val ep = iface.getEndpoint(j)
                    if (ep.direction == UsbConstants.USB_DIR_OUT &&
                        ep.type == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                        lastStatusMessage = "Perangkat USB Bulk OUT terdeteksi: ${dev.productName ?: dev.deviceName}"
                        return dev
                    }
                }
            }
        }

        val names = deviceList.values.joinToString { "${it.productName ?: it.deviceName} (VID:0x${Integer.toHexString(it.vendorId)})" }
        lastStatusMessage = "Perangkat USB tercolok tapi bukan printer yang dikenali ($names)"
        return null
    }

    @JvmStatic
    fun hasPermission(): Boolean {
        val manager = usbManager ?: return false
        val dev = findPrinterDevice() ?: return false
        return manager.hasPermission(dev)
    }

    @JvmStatic
    fun requestPermission(onResult: ((Boolean) -> Unit)? = null) {
        val act = activityRef ?: return
        val manager = usbManager ?: return
        val dev = findPrinterDevice()
        if (dev == null) {
            onResult?.invoke(false)
            return
        }

        if (manager.hasPermission(dev)) {
            lastStatusMessage = "Izin USB sudah ada"
            onResult?.invoke(true)
            return
        }

        this.permissionCallback = onResult
        try {
            val flag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                PendingIntent.FLAG_MUTABLE
            } else {
                0
            }
            // Di Android 12+ (SDK 31+), PendingIntent MUTABLE wajib memiliki intent eksplisit (setPackage)
            val intent = Intent(ACTION_USB_PERMISSION).apply {
                setPackage(act.packageName)
            }
            val permissionIntent = PendingIntent.getBroadcast(
                act, 0, intent, flag
            )
            manager.requestPermission(dev, permissionIntent)
        } catch (e: Exception) {
            Log.e(TAG, "Gagal meminta izin USB: ${e.message}", e)
            lastStatusMessage = "Gagal meminta izin USB: ${e.message}"
            onResult?.invoke(false)
        }
    }

    @JvmStatic
    fun getStatusJson(): String {
        val manager = usbManager
        val json = JSONObject()
        if (manager == null) {
            json.put("ok", false)
            json.put("available", false)
            json.put("message", "USB Manager tidak tersedia")
            return json.toString()
        }

        val dev = findPrinterDevice()
        if (dev == null) {
            json.put("ok", false)
            json.put("available", true)
            json.put("connected", false)
            json.put("message", lastStatusMessage)
            return json.toString()
        }

        val permitted = manager.hasPermission(dev)
        json.put("ok", permitted)
        json.put("available", true)
        json.put("connected", true)
        json.put("has_permission", permitted)
        json.put("device_name", dev.productName ?: dev.deviceName)
        json.put("vendor_id", String.format("0x%04x", dev.vendorId))
        json.put("product_id", String.format("0x%04x", dev.productId))
        json.put("message", if (permitted) "Printer USB siap: ${dev.productName ?: dev.deviceName}"
                           else "Printer USB terdeteksi, butuh izin akses (tekan Minta Izin)")
        return json.toString()
    }

    /**
     * Kirim byte mentah ESC/POS langsung ke printer USB melalui Android USB Host bulkTransfer.
     */
    @JvmStatic
    @Synchronized
    fun printRaw(bytes: ByteArray): Boolean {
        val manager = usbManager
        if (manager == null) {
            Log.e(TAG, "UsbManager null saat printRaw")
            lastStatusMessage = "UsbManager null"
            return false
        }

        val dev = findPrinterDevice()
        if (dev == null) {
            Log.e(TAG, "Tidak ada printer USB terhubung")
            return false
        }

        if (!manager.hasPermission(dev)) {
            Log.e(TAG, "Izin USB belum diberikan untuk printer ini")
            lastStatusMessage = "Izin USB belum diberikan"
            // Coba minta izin untuk cetak berikutnya
            activityRef?.runOnUiThread { requestPermission(null) }
            return false
        }

        // Cari interface dan bulk OUT endpoint
        var targetIface: UsbInterface? = null
        var targetEndpoint: UsbEndpoint? = null

        for (i in 0 until dev.interfaceCount) {
            val iface = dev.getInterface(i)
            for (j in 0 until iface.endpointCount) {
                val ep = iface.getEndpoint(j)
                if (ep.direction == UsbConstants.USB_DIR_OUT &&
                    ep.type == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                    targetIface = iface
                    targetEndpoint = ep
                    break
                }
            }
            if (targetEndpoint != null) break
        }

        if (targetIface == null || targetEndpoint == null) {
            Log.e(TAG, "Tidak ditemukan Bulk OUT endpoint pada printer")
            lastStatusMessage = "Endpoint printer tidak cocok"
            return false
        }

        var connection: UsbDeviceConnection? = null
        try {
            connection = manager.openDevice(dev)
            if (connection == null) {
                Log.e(TAG, "Gagal membuka koneksi USB ke printer")
                lastStatusMessage = "Gagal openDevice"
                return false
            }

            if (!connection.claimInterface(targetIface, true)) {
                Log.e(TAG, "Gagal claim interface printer")
                lastStatusMessage = "Gagal claimInterface"
                return false
            }

            val chunkSize = 4096
            var offset = 0
            val total = bytes.size
            Log.i(TAG, "Mulai kirim data ESC/POS $total bytes ke printer ${dev.deviceName}...")

            while (offset < total) {
                val len = minOf(chunkSize, total - offset)
                val buffer = ByteArray(len)
                System.arraycopy(bytes, offset, buffer, 0, len)

                val sent = connection.bulkTransfer(targetEndpoint, buffer, len, 5000)
                if (sent < 0) {
                    Log.e(TAG, "bulkTransfer error di offset $offset (kode $sent)")
                    lastStatusMessage = "bulkTransfer gagal ($sent)"
                    return false
                }
                offset += sent
            }

            Log.i(TAG, "Berhasil cetak $total bytes ke printer USB!")
            lastStatusMessage = "Cetak berhasil ($total bytes)"
            return true
        } catch (e: Exception) {
            Log.e(TAG, "Exception saat printRaw: ${e.message}", e)
            lastStatusMessage = "Error: ${e.message}"
            return false
        } finally {
            try {
                if (targetIface != null) connection?.releaseInterface(targetIface)
                connection?.close()
            } catch (_: Exception) {}
        }
    }

    @JvmStatic
    fun printBase64(b64: String): Boolean {
        return try {
            val bytes = Base64.decode(b64, Base64.DEFAULT)
            printRaw(bytes)
        } catch (e: Exception) {
            Log.e(TAG, "Error decode base64: ${e.message}")
            false
        }
    }
}

/**
 * Interface Javascript untuk WebView agar UI web bisa langsung cek status & minta izin USB.
 */
class AndroidPrintInterface(private val activity: Activity) {
    @JavascriptInterface
    fun isAvailable(): Boolean = true

    @JavascriptInterface
    fun getStatus(): String = UsbPrinterBridge.getStatusJson()

    @JavascriptInterface
    fun requestPermission() {
        activity.runOnUiThread {
            UsbPrinterBridge.requestPermission { granted ->
                Log.i("AndroidPrintInterface", "Permission result: $granted")
            }
        }
    }

    @JavascriptInterface
    fun printBase64(base64Data: String): Boolean {
        return UsbPrinterBridge.printBase64(base64Data)
    }
}
