package com.rhinobox.samsungremote

import android.util.Base64
import okhttp3.*
import org.json.JSONObject
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.*

class SamsungRemoteClient(private val onStatus: (String, Boolean) -> Unit) {
    private var ws: WebSocket? = null
    private var ip: String = ""
    private var token: String? = null
    private val prefsName = "samsung_remote"
    private var prefs: android.content.SharedPreferences? = null

    fun attach(context: android.content.Context) { prefs = context.getSharedPreferences(prefsName, 0) }

    private fun unsafeClient(): OkHttpClient {
        val trustAll = arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        })
        val sc = SSLContext.getInstance("TLS")
        sc.init(null, trustAll, SecureRandom())
        return OkHttpClient.Builder().sslSocketFactory(sc.socketFactory, trustAll[0] as X509TrustManager)
            .hostnameVerifier { _, _ -> true }.build()
    }

    fun connect(host: String) {
        ip = host.trim()
        if (ip.isBlank()) return
        token = prefs?.getString("token_$ip", null)
        val name = Base64.encodeToString("Samsung Remote".toByteArray(), Base64.NO_WRAP)
        val query = buildString {
            append("name=").append(name)
            token?.let { append("&token=").append(it) }
        }
        val request = Request.Builder().url("wss://$ip:8002/api/v2/channels/samsung.remote.control?$query").build()
        ws?.cancel()
        ws = unsafeClient().newWebSocket(request, listener())
        onStatus("Conectando…", false)
    }

    private fun listener() = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) { onStatus("Esperando autorización del TV…", false) }
        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                val j = JSONObject(text)
                val event = j.optString("event")
                val data = j.optJSONObject("data")
                val newToken = data?.optString("token")
                if (!newToken.isNullOrBlank()) {
                    token = newToken
                    prefs?.edit()?.putString("token_$ip", newToken)?.apply()
                }
                when (event) {
                    "ms.channel.connect" -> onStatus("Conectado", true)
                    "ms.channel.unauthorized" -> onStatus("Autoriza este teléfono en la TV", false)
                }
            } catch (_: Exception) {}
        }
        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            onStatus("Sin conexión", false)
        }
        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { onStatus("Desconectado", false) }
    }

    fun key(key: String) {
        val p = JSONObject().put("Cmd", "Click").put("DataOfCmd", key).put("Option", "false").put("TypeOfRemote", "SendRemoteKey")
        val msg = JSONObject().put("method", "ms.remote.control").put("params", p)
        ws?.send(msg.toString())
    }

    fun text(value: String) {
        val encoded = Base64.encodeToString(value.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
        val p = JSONObject().put("Cmd", encoded).put("DataOfCmd", "base64").put("TypeOfRemote", "SendInputString")
        ws?.send(JSONObject().put("method", "ms.remote.control").put("params", p).toString())
    }
}
