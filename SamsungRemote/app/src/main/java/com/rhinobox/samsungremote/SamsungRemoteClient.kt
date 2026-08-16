package com.rhinobox.samsungremote

import android.util.Base64
import okhttp3.*
import org.json.JSONObject
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.*

class SamsungRemoteClient(private val onStatus: (String, Boolean) -> Unit) {
    private var ws: WebSocket? = null
    private var ip: String = ""
    private var token: String? = null
    private var triedPlain = false
    private var prefs: android.content.SharedPreferences? = null

    fun attach(context: android.content.Context) {
        prefs = context.getSharedPreferences("samsung_remote", 0)
    }

    private fun client(): OkHttpClient {
        val trustAll = arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        })
        val sc = SSLContext.getInstance("TLS")
        sc.init(null, trustAll, SecureRandom())
        return OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS)
            .sslSocketFactory(sc.socketFactory, trustAll[0] as X509TrustManager)
            .hostnameVerifier { _, _ -> true }
            .build()
    }

    fun connect(host: String) {
        ip = host.trim()
        if (ip.isBlank()) return
        token = prefs?.getString("token_$ip", null)
        triedPlain = false
        connectSecure()
    }

    private fun connectSecure() {
        onStatus("Conectando a $ip…", false)
        open("wss://$ip:8002/api/v2/channels/samsung.remote.control")
    }

    private fun connectPlain() {
        triedPlain = true
        onStatus("Probando conexión alternativa…", false)
        open("ws://$ip:8001/api/v2/channels/samsung.remote.control")
    }

    private fun open(base: String) {
        val name = Base64.encodeToString("Samsung Remote".toByteArray(), Base64.NO_WRAP)
        val url = buildString {
            append(base).append("?name=").append(name)
            token?.let { append("&token=").append(it) }
        }
        ws?.cancel()
        ws = client().newWebSocket(Request.Builder().url(url).build(), listener())
    }

    private fun listener() = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            onStatus("Esperando permiso en la TV…", false)
        }

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
                    "ms.channel.connect" -> {
                        prefs?.edit()?.putString("last_ip", ip)?.apply()
                        onStatus("Conectado", true)
                    }
                    "ms.channel.unauthorized" -> onStatus("Acepta el permiso en la TV", false)
                }
            } catch (_: Exception) { }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            if (!triedPlain) connectPlain() else onStatus("No se pudo conectar", false)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            onStatus("Desconectado", false)
        }
    }

    fun disconnect() {
        ws?.close(1000, "bye")
        ws = null
        onStatus("Sin conexión", false)
    }

    fun key(key: String) {
        val p = JSONObject()
            .put("Cmd", "Click")
            .put("DataOfCmd", key)
            .put("Option", "false")
            .put("TypeOfRemote", "SendRemoteKey")
        ws?.send(JSONObject().put("method", "ms.remote.control").put("params", p).toString())
    }

    fun text(value: String) {
        val encoded = Base64.encodeToString(value.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
        val p = JSONObject()
            .put("Cmd", encoded)
            .put("DataOfCmd", "base64")
            .put("TypeOfRemote", "SendInputString")
        ws?.send(JSONObject().put("method", "ms.remote.control").put("params", p).toString())
    }
}
