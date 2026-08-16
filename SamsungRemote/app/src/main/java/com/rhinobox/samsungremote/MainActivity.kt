package com.rhinobox.samsungremote

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.*
import kotlin.math.abs

class MainActivity : Activity() {
    private lateinit var remote: SamsungRemoteClient
    private lateinit var status: TextView
    private lateinit var tvName: TextView
    private lateinit var contentHost: FrameLayout
    private lateinit var prefs: android.content.SharedPreferences

    private val bg = Color.rgb(244, 247, 252)
    private val ink = Color.rgb(25, 31, 40)
    private val soft = Color.rgb(251, 252, 255)
    private val accent = Color.rgb(83, 95, 232)
    private val danger = Color.rgb(210, 45, 45)

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("samsung_remote", 0)
        remote = SamsungRemoteClient { s, ok ->
            runOnUiThread {
                status.text = if (ok) "● $s" else "● $s"
                status.setTextColor(if (ok) Color.rgb(24, 181, 94) else Color.rgb(120, 126, 136))
            }
        }
        remote.attach(this)
        buildUi()
        requestNetworkPermissionAndDiscover()
    }

    private fun shape(color: Int = soft, radius: Float = 28f, stroke: Int? = null): GradientDrawable {
        return GradientDrawable().apply {
            cornerRadius = radius * resources.displayMetrics.density
            setColor(color)
            if (stroke != null) setStroke(1.dp, stroke)
        }
    }

    private fun label(text: String, size: Float = 14f, bold: Boolean = false): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(ink)
            gravity = Gravity.CENTER
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }
    }

    private fun keyButton(text: String, key: String? = null, dangerButton: Boolean = false, action: (() -> Unit)? = null): Button {
        return Button(this).apply {
            this.text = text
            textSize = 13f
            isAllCaps = false
            setTextColor(if (dangerButton) danger else ink)
            background = shape(soft, 26f)
            elevation = 7.dp.toFloat()
            stateListAnimator = null
            setPadding(5.dp, 4.dp, 5.dp, 4.dp)
            setOnClickListener {
                performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP)
                if (action != null) action() else key?.let { remote.key(it) }
            }
        }
    }

    private fun addWeighted(row: LinearLayout, v: View, weight: Float = 1f, height: Int = 72) {
        row.addView(v, LinearLayout.LayoutParams(0, height.dp, weight).apply { setMargins(6.dp, 6.dp, 6.dp, 6.dp) })
    }

    private fun buildUi() {
        val scroll = ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            clipToPadding = false
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18.dp, 16.dp, 18.dp, 28.dp)
        }
        scroll.addView(root)
        setContentView(scroll)

        val header = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val power = keyButton("⏻", "KEY_POWER", true).apply { textSize = 29f }
        header.addView(power, LinearLayout.LayoutParams(72.dp, 72.dp))

        val center = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        tvName = label("Samsung TV", 20f, true)
        status = label("● Buscando TV…", 12f)
        center.addView(tvName, LinearLayout.LayoutParams(-1, 34.dp))
        center.addView(status, LinearLayout.LayoutParams(-1, 25.dp))
        header.addView(center, LinearLayout.LayoutParams(0, 74.dp, 1f))

        val discover = keyButton("⌁", action = { discoverTvs() }).apply { textSize = 26f }
        header.addView(discover, LinearLayout.LayoutParams(72.dp, 72.dp))
        root.addView(header)

        val upper = LinearLayout(this).apply { gravity = Gravity.CENTER }
        val volume = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = shape(soft, 30f)
            elevation = 7.dp.toFloat()
            addView(keyButton("＋", "KEY_VOLUP").apply { elevation = 0f; background = null; textSize = 31f }, LinearLayout.LayoutParams(-1, 88.dp))
            addView(label("VOL", 13f), LinearLayout.LayoutParams(-1, 42.dp))
            addView(keyButton("−", "KEY_VOLDOWN").apply { elevation = 0f; background = null; textSize = 31f }, LinearLayout.LayoutParams(-1, 88.dp))
        }
        upper.addView(volume, LinearLayout.LayoutParams(84.dp, 218.dp).apply { setMargins(0, 10.dp, 7.dp, 10.dp) })

        val middle = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val r1 = LinearLayout(this)
        addWeighted(r1, keyButton("🔇\nMUTE", "KEY_MUTE"), 1f, 98)
        addWeighted(r1, keyButton("↪\nEXIT", "KEY_EXIT"), 1f, 98)
        middle.addView(r1)
        val r2 = LinearLayout(this)
        addWeighted(r2, keyButton("⌂\nHOME", "KEY_HOME"), 1f, 98)
        addWeighted(r2, keyButton("↶\nBACK", "KEY_RETURN"), 1f, 98)
        middle.addView(r2)
        upper.addView(middle, LinearLayout.LayoutParams(0, -2, 1f))

        val channel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = shape(soft, 30f)
            elevation = 7.dp.toFloat()
            addView(keyButton("⌃", "KEY_CHUP").apply { elevation = 0f; background = null; textSize = 30f }, LinearLayout.LayoutParams(-1, 88.dp))
            addView(label("CH", 13f), LinearLayout.LayoutParams(-1, 42.dp))
            addView(keyButton("⌄", "KEY_CHDOWN").apply { elevation = 0f; background = null; textSize = 30f }, LinearLayout.LayoutParams(-1, 88.dp))
        }
        upper.addView(channel, LinearLayout.LayoutParams(84.dp, 218.dp).apply { setMargins(7.dp, 10.dp, 0, 10.dp) })
        root.addView(upper)

        contentHost = FrameLayout(this)
        root.addView(contentHost, LinearLayout.LayoutParams(-1, 390.dp).apply { setMargins(0, 8.dp, 0, 4.dp) })
        showDirectional()

        val modeBar = LinearLayout(this).apply {
            gravity = Gravity.CENTER
            background = shape(Color.rgb(248, 250, 254), 30f, Color.rgb(230, 234, 241))
            setPadding(6.dp, 5.dp, 6.dp, 5.dp)
        }
        addWeighted(modeBar, keyButton("◉", action = { showDirectional() }).apply { elevation = 0f }, 1f, 58)
        addWeighted(modeBar, keyButton("▭", action = { showTouchpad() }).apply { elevation = 0f }, 1f, 58)
        addWeighted(modeBar, keyButton("123", action = { showNumbers() }).apply { elevation = 0f }, 1f, 58)
        root.addView(modeBar, LinearLayout.LayoutParams(-1, 74.dp).apply { setMargins(36.dp, 8.dp, 36.dp, 12.dp) })

        val tools = LinearLayout(this)
        addWeighted(tools, keyButton("⌕\nSEARCH", "KEY_SEARCH"), 1f, 78)
        addWeighted(tools, keyButton("⌨\nKEYBOARD", action = { keyboardDialog() }), 1f, 78)
        addWeighted(tools, keyButton("↪\nSOURCE", "KEY_SOURCE"), 1f, 78)
        addWeighted(tools, keyButton("▤\nE-MANUAL", "KEY_E-MANUAL"), 1f, 78)
        root.addView(tools)

        val media = LinearLayout(this)
        addWeighted(media, keyButton("⏪", "KEY_REWIND"), 1f, 66)
        addWeighted(media, keyButton("▶Ⅱ", "KEY_PLAY"), 1f, 66)
        addWeighted(media, keyButton("⏩", "KEY_FF"), 1f, 66)
        addWeighted(media, keyButton("■", "KEY_STOP"), 1f, 66)
        root.addView(media)

        val more = LinearLayout(this)
        addWeighted(more, keyButton("INFO", "KEY_INFO"), 1f, 62)
        addWeighted(more, keyButton("GUIDE", "KEY_GUIDE"), 1f, 62)
        addWeighted(more, keyButton("MENU", "KEY_MENU"), 1f, 62)
        addWeighted(more, keyButton("CH-LIST", "KEY_CH_LIST"), 1f, 62)
        root.addView(more)
    }

    private fun showDirectional() {
        contentHost.removeAllViews()
        val pad = FrameLayout(this).apply {
            background = shape(soft, 180f)
            elevation = 8.dp.toFloat()
        }
        fun place(v: View, w: Int, h: Int, gravity: Int, ml: Int = 0, mt: Int = 0, mr: Int = 0, mb: Int = 0) {
            pad.addView(v, FrameLayout.LayoutParams(w.dp, h.dp, gravity).apply {
                setMargins(ml.dp, mt.dp, mr.dp, mb.dp)
            })
        }
        place(keyButton("⌃", "KEY_UP").apply { elevation = 0f; background = null; textSize = 34f }, 100, 82, Gravity.TOP or Gravity.CENTER_HORIZONTAL, mt = 20)
        place(keyButton("‹", "KEY_LEFT").apply { elevation = 0f; background = null; textSize = 42f }, 90, 100, Gravity.CENTER_VERTICAL or Gravity.LEFT, ml = 20)
        place(keyButton("OK", "KEY_ENTER").apply { background = shape(Color.rgb(248, 249, 252), 70f); textSize = 17f }, 118, 118, Gravity.CENTER)
        place(keyButton("›", "KEY_RIGHT").apply { elevation = 0f; background = null; textSize = 42f }, 90, 100, Gravity.CENTER_VERTICAL or Gravity.RIGHT, mr = 20)
        place(keyButton("⌄", "KEY_DOWN").apply { elevation = 0f; background = null; textSize = 34f }, 100, 82, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL, mb = 20)
        contentHost.addView(pad, FrameLayout.LayoutParams(-1, 360.dp).apply { setMargins(28.dp, 12.dp, 28.dp, 8.dp) })
    }

    private fun showNumbers() {
        contentHost.removeAllViews()
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        listOf(listOf("1","2","3"), listOf("4","5","6"), listOf("7","8","9"), listOf("PRE-CH","0","CH-LIST")).forEach { items ->
            val row = LinearLayout(this)
            items.forEach { t ->
                val key = when (t) { "PRE-CH" -> "KEY_PRECH"; "CH-LIST" -> "KEY_CH_LIST"; else -> "KEY_$t" }
                addWeighted(row, keyButton(t, key).apply { textSize = if (t.length == 1) 24f else 12f }, 1f, 76)
            }
            box.addView(row)
        }
        contentHost.addView(box, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showTouchpad() {
        contentHost.removeAllViews()
        val pad = TouchPadView(this) { key -> remote.key(key) }.apply {
            background = dottedLikeBackground()
            elevation = 7.dp.toFloat()
        }
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            addView(pad, LinearLayout.LayoutParams(-1, 285.dp).apply { setMargins(12.dp, 24.dp, 12.dp, 8.dp) })
            addView(label("Desliza para navegar · toca para OK", 12f), LinearLayout.LayoutParams(-1, 38.dp))
        }
        contentHost.addView(wrap, FrameLayout.LayoutParams(-1, -1))
    }

    private fun dottedLikeBackground(): GradientDrawable = shape(Color.rgb(249, 251, 254), 26f, Color.rgb(228, 232, 239))

    private fun keyboardDialog() {
        val input = EditText(this).apply { hint = "Escribe en tu TV"; minLines = 2; setPadding(18.dp, 16.dp, 18.dp, 16.dp) }
        AlertDialog.Builder(this)
            .setTitle("Teclado")
            .setView(input)
            .setPositiveButton("ENVIAR") { _, _ -> remote.text(input.text.toString()) }
            .setNegativeButton("CANCELAR", null)
            .show()
        input.requestFocus()
        input.postDelayed({
            (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
        }, 250)
    }

    private fun requestNetworkPermissionAndDiscover() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.NEARBY_WIFI_DEVICES), 77)
        } else discoverTvs()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 77) discoverTvs()
    }

    private fun discoverTvs() {
        status.text = "● Buscando en tu Wi‑Fi…"
        SamsungTvDiscovery.discover(this,
            onStatus = { msg -> runOnUiThread { status.text = "● $msg" } },
            onDone = { tvs -> runOnUiThread {
                if (tvs.isEmpty()) {
                    status.text = "● No encontré el TV"
                    manualFallbackDialog()
                } else if (tvs.size == 1) {
                    connectTv(tvs.first())
                } else {
                    val labels = tvs.map { "${it.name}\n${it.model} · ${it.ip}" }.toTypedArray()
                    AlertDialog.Builder(this)
                        .setTitle("Selecciona tu Samsung TV")
                        .setItems(labels) { _, which -> connectTv(tvs[which]) }
                        .setNegativeButton("CANCELAR", null)
                        .show()
                }
            } }
        )
    }

    private fun connectTv(tv: SamsungTvDiscovery.Tv) {
        tvName.text = tv.name.ifBlank { "Samsung TV" }
        prefs.edit().putString("last_ip", tv.ip).apply()
        remote.connect(tv.ip)
    }

    private fun manualFallbackDialog() {
        val saved = prefs.getString("last_ip", "") ?: ""
        val input = EditText(this).apply { hint = "IP del TV"; setText(saved); setPadding(18.dp, 8.dp, 18.dp, 8.dp) }
        AlertDialog.Builder(this)
            .setTitle("No encontré el TV automáticamente")
            .setMessage("Verifica que teléfono y TV estén en la misma Wi‑Fi. Puedes reintentar o escribir la IP solo como alternativa.")
            .setView(input)
            .setPositiveButton("CONECTAR") { _, _ ->
                val ip = input.text.toString().trim()
                if (ip.isNotBlank()) remote.connect(ip)
            }
            .setNeutralButton("BUSCAR OTRA VEZ") { _, _ -> discoverTvs() }
            .setNegativeButton("CANCELAR", null)
            .show()
    }

    private class TouchPadView(context: Context, private val send: (String) -> Unit) : View(context) {
        private var downX = 0f
        private var downY = 0f
        private var downTime = 0L

        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.x; downY = event.y; downTime = System.currentTimeMillis(); return true
                }
                MotionEvent.ACTION_UP -> {
                    val dx = event.x - downX
                    val dy = event.y - downY
                    if (abs(dx) < 35 && abs(dy) < 35) send("KEY_ENTER")
                    else if (abs(dx) > abs(dy)) send(if (dx > 0) "KEY_RIGHT" else "KEY_LEFT")
                    else send(if (dy > 0) "KEY_DOWN" else "KEY_UP")
                    performClick()
                    return true
                }
            }
            return true
        }

        override fun performClick(): Boolean { super.performClick(); return true }
    }
}