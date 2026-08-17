package com.rhinobox.samsungremote

import android.content.Context
import android.net.wifi.WifiManager
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.*
import java.util.Collections
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

object SamsungTvDiscovery {
    data class Tv(val name: String, val ip: String, val model: String = "Samsung TV")

    fun discover(context: Context, onStatus: (String) -> Unit, onDone: (List<Tv>) -> Unit) {
        Thread {
            val found = Collections.synchronizedMap(linkedMapOf<String, Tv>())
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val lock = wifi.createMulticastLock("samsung_remote_discovery").apply { setReferenceCounted(false); acquire() }
            try {
                onStatus("Buscando Samsung TV en tu Wi‑Fi…")
                ssdp(found)
                if (found.isEmpty()) {
                    onStatus("Buscando dispositivos compatibles…")
                    scanSubnet(found)
                }
            } catch (_: Exception) { }
            finally { try { lock.release() } catch (_: Exception) {} }
            onDone(found.values.toList())
        }.start()
    }

    private fun ssdp(found: MutableMap<String, Tv>) {
        val socket = DatagramSocket().apply { soTimeout = 650 }
        val msg = ("M-SEARCH * HTTP/1.1\r\n" +
                "HOST:239.255.255.250:1900\r\n" +
                "MAN:\"ssdp:discover\"\r\n" +
                "MX:1\r\n" +
                "ST:ssdp:all\r\n\r\n").toByteArray()
        val group = InetAddress.getByName("239.255.255.250")
        repeat(2) { socket.send(DatagramPacket(msg, msg.size, group, 1900)) }
        val end = System.currentTimeMillis() + 2500
        val buf = ByteArray(8192)
        while (System.currentTimeMillis() < end) {
            try {
                val p = DatagramPacket(buf, buf.size)
                socket.receive(p)
                val text = String(p.data, 0, p.length)
                val host = p.address.hostAddress ?: continue
                if (text.contains("samsung", true) || text.contains("smarttv", true)) {
                    inspect(host)?.let { found[host] = it }
                }
            } catch (_: SocketTimeoutException) { }
        }
        socket.close()
    }

    private fun localAddress(): String? {
        return try {
            DatagramSocket().use { s ->
                s.connect(InetAddress.getByName("8.8.8.8"), 53)
                s.localAddress.hostAddress
            }
        } catch (_: Exception) { null }
    }

    private fun scanSubnet(found: MutableMap<String, Tv>) {
        val local = localAddress() ?: return
        val parts = local.split('.')
        if (parts.size != 4) return
        val prefix = parts.take(3).joinToString(".")
        val pool = Executors.newFixedThreadPool(36)
        for (i in 1..254) {
            val host = "$prefix.$i"
            if (host == local) continue
            pool.submit {
                if (portOpen(host, 8001) || portOpen(host, 8002)) {
                    inspect(host)?.let { found[host] = it }
                }
            }
        }
        pool.shutdown()
        pool.awaitTermination(7, TimeUnit.SECONDS)
    }

    private fun portOpen(host: String, port: Int): Boolean {
        return try {
            Socket().use { it.connect(InetSocketAddress(host, port), 280) }
            true
        } catch (_: Exception) { false }
    }

    private fun inspect(host: String): Tv? {
        val client = OkHttpClient.Builder().connectTimeout(650, TimeUnit.MILLISECONDS).readTimeout(900, TimeUnit.MILLISECONDS).build()
        val urls = listOf("http://$host:8001/api/v2/", "http://$host:8001/api/v2")
        for (url in urls) {
            try {
                client.newCall(Request.Builder().url(url).build()).execute().use { r ->
                    val body = r.body?.string().orEmpty()
                    if (body.isBlank()) return@use
                    val j = JSONObject(body)
                    val device = j.optJSONObject("device") ?: j
                    val name = device.optString("name").ifBlank { "Samsung TV" }
                    val model = device.optString("modelName").ifBlank { device.optString("model").ifBlank { "Samsung TV" } }
                    if (body.contains("samsung", true) || model.isNotBlank()) return Tv(name, host, model)
                }
            } catch (_: Exception) { }
        }
        return null
    }
}
