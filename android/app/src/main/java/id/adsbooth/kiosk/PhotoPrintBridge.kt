package id.adsbooth.kiosk

import android.app.Activity
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.RectF
import android.os.Bundle
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import android.print.pdf.PrintedPdfDocument
import android.webkit.JavascriptInterface
import org.json.JSONObject
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Jembatan cetak FOTO 4R ke printer LAN (Mopria / AirPrint / Epson / Canon, dll)
 * lewat Android Print Framework. Dipanggil dari web:
 *   window.AndroidPhotoPrinter.printPhoto(url, copies, media, borderless)
 * Printer dipilih lewat dialog cetak sistem (print-service yang terpasang
 * di tablet menemukan printer di jaringan yang sama).
 */
class PhotoPrintBridge(private val activity: Activity) {

    @JavascriptInterface
    fun printPhoto(url: String, copies: String, media: String, borderless: Boolean): String {
        return try {
            val n = (copies.toIntOrNull() ?: 1).coerceIn(1, 20)
            Handler(Looper.getMainLooper()).post { startPrint(url, n, media, borderless) }
            JSONObject().put("ok", true).toString()
        } catch (e: Exception) {
            JSONObject().put("ok", false).put("message", e.message ?: "print error").toString()
        }
    }

    private fun mediaSize(media: String): PrintAttributes.MediaSize =
        when (media.lowercase().replace(" ", "").replace("cm", "")) {
            "a4" -> PrintAttributes.MediaSize.ISO_A4
            "a5" -> PrintAttributes.MediaSize.ISO_A5
            "a6" -> PrintAttributes.MediaSize.ISO_A6
            "5x7", "13x18" -> PrintAttributes.MediaSize.NA_5X7
            "l", "3.5x5", "9x13" -> PrintAttributes.MediaSize.NA_INDEX_4X6
            else -> PrintAttributes.MediaSize.NA_INDEX_4X6   // 4x6 / postcard / 10x15 (default)
        }

    private fun startPrint(url: String, copies: Int, media: String, borderless: Boolean) {
        val pm = activity.getSystemService(Context.PRINT_SERVICE) as PrintManager
        val attrs = PrintAttributes.Builder()
            .setMediaSize(mediaSize(media))
            .setResolution(PrintAttributes.Resolution("adsbooth", "300dpi", 300, 300))
            .setColorMode(PrintAttributes.COLOR_MODE_COLOR)
            .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
            .build()
        pm.print("AdsBooth Photo", BitmapPrintAdapter(activity, url, copies), attrs)
    }
}

private class BitmapPrintAdapter(
    private val ctx: Context,
    private val url: String,
    private val copies: Int
) : PrintDocumentAdapter() {

    private var bitmap: Bitmap? = null
    private var attrs: PrintAttributes? = null

    override fun onLayout(
        old: PrintAttributes?, new: PrintAttributes?, cancel: CancellationSignal?,
        cb: LayoutResultCallback, extras: Bundle?
    ) {
        attrs = new
        if (cancel?.isCanceled == true) { cb.onLayoutCancelled(); return }
        Thread {
            try {
                if (bitmap == null) bitmap = fetchBitmap(url)
                val info = PrintDocumentInfo.Builder("adsbooth_photo.pdf")
                    .setContentType(PrintDocumentInfo.CONTENT_TYPE_PHOTO)
                    .setPageCount(copies)
                    .build()
                Handler(Looper.getMainLooper()).post { cb.onLayoutFinished(info, true) }
            } catch (e: Exception) {
                Handler(Looper.getMainLooper()).post { cb.onLayoutFailed(e.message ?: "layout error") }
            }
        }.start()
    }

    override fun onWrite(
        pages: Array<out PageRange>?, dest: ParcelFileDescriptor,
        cancel: CancellationSignal?, cb: WriteResultCallback
    ) {
        try {
            val pdf = PrintedPdfDocument(ctx, attrs!!)
            for (i in 0 until copies.coerceAtLeast(1)) {
                if (cancel?.isCanceled == true) { pdf.close(); cb.onWriteCancelled(); return }
                val page = pdf.startPage(i)
                drawCover(page.canvas, bitmap!!)
                pdf.finishPage(page)
            }
            pdf.writeTo(FileOutputStream(dest.fileDescriptor))
            pdf.close()
            cb.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
        } catch (e: Exception) {
            cb.onWriteFailed(e.message ?: "write error")
        }
    }

    private fun drawCover(canvas: android.graphics.Canvas, src: Bitmap) {
        val pw = canvas.width.toFloat()
        val ph = canvas.height.toFloat()
        var b = src
        if ((b.width > b.height) != (pw > ph)) {
            val m = Matrix(); m.postRotate(90f)
            b = Bitmap.createBitmap(src, 0, 0, src.width, src.height, m, true)
        }
        val scale = maxOf(pw / b.width, ph / b.height)   // cover: isi penuh kertas
        val w = b.width * scale
        val h = b.height * scale
        val left = (pw - w) / 2f
        val top = (ph - h) / 2f
        canvas.drawBitmap(b, null, RectF(left, top, left + w, top + h), null)
    }

    private fun fetchBitmap(u: String): Bitmap {
        val conn = URL(u).openConnection() as HttpURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.inputStream.use {
            return BitmapFactory.decodeStream(it) ?: throw RuntimeException("Gagal decode gambar")
        }
    }
}