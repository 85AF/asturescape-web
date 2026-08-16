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
import android.view.Window
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.math.abs

class MainActivity : Activity() {
    private lateinit var remote: SamsungRemoteClient
    private lateinit var status: TextView
    private lateinit var tvName: TextView
    private lateinit var contentHost: FrameLayout
    private lateinit var prefs: android.content.SharedPreferences

    private val bg = Color.rgb(246, 248, 252)
    private val card = Color.WHITE
    private val ink = Color.rgb(24, 28, 36)
    private val muted = Color.rgb(121, 128, 140)
    private val border = Color.rgb(229, 233, 240)
    private val accent = Color.rgb(82, 91, 235)
    private val green = Color.rgb(38, 196, 103)
    private val red = Color.rgb(238, 53, 66)

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestWindowFeature(Window.FEATURE_NO_TITLE)
        window.statusBarColor = bg
        window.navigationBarColor = bg
        if (Build.VERSION.SDK_INT >= 23) window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR

        prefs = getSharedPreferences("samsung_remote", 0)
        remote = SamsungRemoteClient { s, ok ->
            runOnUiThread {
                status.text = "●  $s"
                status.setTextColor(if (ok) green else muted)
            }
        }
        remote.attach(this)
        buildUi()
        requestNetworkPermissionAndDiscover()
    }

    private fun shape(color: Int = card, radiusDp: Float = 20f, strokeColor: Int? = border, strokeWidthDp: Int = 1): GradientDrawable =
        GradientDrawable().apply {
            cornerRadius = radiusDp * resources.displayMetrics.density
            setColor(color)
            if (strokeColor != null) setStroke(strokeWidthDp.dp, strokeColor)
        }

    private fun textLabel(text: String, size: Float, color: Int = ink, bold: Boolean = false): TextView =
        TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            gravity = Gravity.CENTER
            includeFontPadding = false
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    private fun cardButton(
        text: String,
        key: String? = null,
        size: Float = 13f,
        textColor: Int = ink,
        radius: Float = 20f,
        elevationDp: Int = 2,
        action: (() -> Unit)? = null
    ): TextView = textLabel(text, size, textColor).apply {
        background = shape(card, radius)
        elevation = elevationDp.dp.toFloat()
        setPadding(4.dp, 3.dp, 4.dp, 3.dp)
        isClickable = true
        isFocusable = true
        setOnClickListener {
            performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP)
            if (action != null) action() else key?.let { remote.key(it) }
        }
    }

    private fun addWeighted(row: LinearLayout, view: View, heightDp: Int, weight: Float = 1f, marginDp: Int = 3) {
        row.addView(view, LinearLayout.LayoutParams(0, heightDp.dp, weight).apply {
            setMargins(marginDp.dp, marginDp.dp, marginDp.dp, marginDp.dp)
        })
    }

    private fun buildUi() {
        val scroll = ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            clipToPadding = false
            overScrollMode = View.OVER_SCROLL_NEVER
            isVerticalScrollBarEnabled = false
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(14.dp, 6.dp, 14.dp, 8.dp)
        }
        scroll.addView(root)
        setContentView(scroll)

        val header = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val power = cardButton("⏻", "KEY_POWER", 25f, red, 26f, 3)
        header.addView(power, LinearLayout.LayoutParams(54.dp, 54.dp).apply { setMargins(0, 0, 6.dp, 0) })

        val center = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        tvName = textLabel("Samsung TV", 19f, ink, true)
        status = textLabel("●  Buscando TV…", 11f, muted)
        center.addView(tvName, LinearLayout.LayoutParams(-1, 28.dp))
        center.addView(status, LinearLayout.LayoutParams(-1, 20.dp))
        header.addView(center, LinearLayout.LayoutParams(0, 54.dp, 1f))

        val discover = cardButton("⌁", size = 22f, radius = 26f, elevationDp = 3, action = { discoverTvs() })
        header.addView(discover, LinearLayout.LayoutParams(54.dp, 54.dp).apply { setMargins(6.dp, 0, 0, 0) })
        root.addView(header)

        val upper = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(0, 6.dp, 0, 0) }
        val volume = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            background = shape(card, 26f); elevation = 3.dp.toFloat()
            addView(cardButton("＋", "KEY_VOLUP", 25f, elevationDp = 0).apply { background = null }, LinearLayout.LayoutParams(-1, 49.dp))
            addView(textLabel("VOL", 11f, ink, true), LinearLayout.LayoutParams(-1, 24.dp))
            addView(cardButton("−", "KEY_VOLDOWN", 25f, elevationDp = 0).apply { background = null }, LinearLayout.LayoutParams(-1, 49.dp))
        }
        upper.addView(volume, LinearLayout.LayoutParams(66.dp, 122.dp).apply { setMargins(0, 2.dp, 4.dp, 2.dp) })

        val middle = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val r1 = LinearLayout(this)
        addWeighted(r1, cardButton("⌁\nMUTE", "KEY_MUTE", 11f), 56)
        addWeighted(r1, cardButton("↪\nEXIT", "KEY_EXIT", 11f), 56)
        middle.addView(r1)
        val r2 = LinearLayout(this)
        addWeighted(r2, cardButton("⌂\nHOME", "KEY_HOME", 11f), 56)
        addWeighted(r2, cardButton("↶\nBACK", "KEY_RETURN", 11f), 56)
        middle.addView(r2)
        upper.addView(middle, LinearLayout.LayoutParams(0, 122.dp, 1f))

        val channel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            background = shape(card, 26f); elevation = 3.dp.toFloat()
            addView(cardButton("⌃", "KEY_CHUP", 24f, elevationDp = 0).apply { background = null }, LinearLayout.LayoutParams(-1, 49.dp))
            addView(textLabel("CH", 11f, ink, true), LinearLayout.LayoutParams(-1, 24.dp))
            addView(cardButton("⌄", "KEY_CHDOWN", 24f, elevationDp = 0).apply { background = null }, LinearLayout.LayoutParams(-1, 49.dp))
        }
        upper.addView(channel, LinearLayout.LayoutParams(66.dp, 122.dp).apply { setMargins(4.dp, 2.dp, 0, 2.dp) })
        root.addView(upper)

        contentHost = FrameLayout(this)
        root.addView(contentHost, LinearLayout.LayoutParams(-1, 224.dp).apply { setMargins(0, 4.dp, 0, 2.dp) })
        showDirectional()

        val modeBar = LinearLayout(this).apply {
            gravity = Gravity.CENTER
            background = shape(Color.rgb(250, 251, 254), 25f, border)
            setPadding(3.dp, 2.dp, 3.dp, 2.dp)
            elevation = 1.dp.toFloat()
        }
        addWeighted(modeBar, cardButton("◉", size = 16f, radius = 20f, elevationDp = 0, action = { showDirectional() }), 40, marginDp = 1)
        addWeighted(modeBar, cardButton("▭", size = 16f, radius = 20f, elevationDp = 0, action = { showTouchpad() }), 40, marginDp = 1)
        addWeighted(modeBar, cardButton("123", size = 14f, radius = 20f, elevationDp = 0, action = { showNumbers() }), 40, marginDp = 1)
        root.addView(modeBar, LinearLayout.LayoutParams(-1, 46.dp).apply { setMargins(52.dp, 2.dp, 52.dp, 5.dp) })

        val tools = LinearLayout(this)
        addWeighted(tools, cardButton("⌕\nSEARCH", "KEY_SEARCH", 9.5f), 50, marginDp = 3)
        addWeighted(tools, cardButton("⌨\nKEYBOARD", size = 9.5f, action = { keyboardDialog() }), 50, marginDp = 3)
        addWeighted(tools, cardButton("↪\nSOURCE", "KEY_SOURCE", 9.5f), 50, marginDp = 3)
        addWeighted(tools, cardButton("▤\nE-MANUAL", "KEY_E-MANUAL", 9.5f), 50, marginDp = 3)
        root.addView(tools)

        val media = LinearLayout(this)
        addWeighted(media, cardButton("◀◀", "KEY_REWIND", 15f), 44, marginDp = 3)
        addWeighted(media, cardButton("▶Ⅱ", "KEY_PLAY", 15f), 44, marginDp = 3)
        addWeighted(media, cardButton("▶▶", "KEY_FF", 15f, accent), 44, marginDp = 3)
        addWeighted(media, cardButton("■", "KEY_STOP", 15f), 44, marginDp = 3)
        root.addView(media)

        val more = LinearLayout(this)
        addWeighted(more, cardButton("INFO", "KEY_INFO", 9.5f), 40, marginDp = 3)
        addWeighted(more, cardButton("GUIDE", "KEY_GUIDE", 9.5f), 40, marginDp = 3)
        addWeighted(more, cardButton("MENU", "KEY_MENU", 9.5f), 40, marginDp = 3)
        addWeighted(more, cardButton("CH-LIST", "KEY_CH_LIST", 9.5f), 40, marginDp = 3)
        root.addView(more)
    }

    private fun showDirectional() {
        contentHost.removeAllViews()
        val pad = FrameLayout(this).apply { background = shape(card, 112f); elevation = 4.dp.toFloat() }
        fun place(view: View, w: Int, h: Int, gravity: Int, ml: Int = 0, mt: Int = 0, mr: Int = 0, mb: Int = 0) {
            pad.addView(view, FrameLayout.LayoutParams(w.dp, h.dp, gravity).apply { setMargins(ml.dp, mt.dp, mr.dp, mb.dp) })
        }
        place(cardButton("⌃", "KEY_UP", 24f, elevationDp = 0).apply { background = null }, 66, 46, Gravity.TOP or Gravity.CENTER_HORIZONTAL, mt = 8)
        place(cardButton("‹", "KEY_LEFT", 34f, elevationDp = 0).apply { background = null }, 56, 66, Gravity.CENTER_VERTICAL or Gravity.LEFT, ml = 8)
        place(cardButton("OK", "KEY_ENTER", 16f, radius = 44f, elevationDp = 2).apply { background = shape(Color.rgb(250,251,254), 44f, accent) }, 88, 88, Gravity.CENTER)
        place(cardButton("›", "KEY_RIGHT", 34f, elevationDp = 0).apply { background = null }, 56, 66, Gravity.CENTER_VERTICAL or Gravity.RIGHT, mr = 8)
        place(cardButton("⌄", "KEY_DOWN", 24f, elevationDp = 0).apply { background = null }, 66, 46, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL, mb = 8)
        contentHost.addView(pad, FrameLayout.LayoutParams(214.dp, 214.dp, Gravity.CENTER))
    }

    private fun showTouchpad() {
        contentHost.removeAllViews()
        val pad = TouchPadView(this) { key -> remote.key(key) }.apply { background = shape(card, 24f, border); elevation = 3.dp.toFloat() }
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            addView(pad, LinearLayout.LayoutParams(-1, 170.dp).apply { setMargins(8.dp, 8.dp, 8.dp, 2.dp) })
            addView(textLabel("Desliza para navegar · toca para OK", 10f, muted), LinearLayout.LayoutParams(-1, 28.dp))
        }
        contentHost.addView(wrap, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showNumbers() {
        contentHost.removeAllViews()
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(8.dp, 2.dp, 8.dp, 2.dp)
        }
        val rows = listOf(
            listOf("1", "2", "3"), listOf("4", "5", "6"),
            listOf("7", "8", "9"), listOf("PRE-CH", "0", "CH-LIST")
        )
        rows.forEach { items ->
            val row = LinearLayout(this)
            items.forEach { t ->
                val key = when (t) {
                    "PRE-CH" -> "KEY_PRECH"
                    "CH-LIST" -> "KEY_CH_LIST"
                    else -> "KEY_$t"
                }
                addWeighted(row, cardButton(t, key, if (t.length == 1) 17f else 9f, radius = 21f), 44, marginDp = 2)
            }
            box.addView(row, LinearLayout.LayoutParams(-1, 50.dp))
        }
        contentHost.addView(box, FrameLayout.LayoutParams(-1, -1))
    }

    private fun keyboardDialog() {
        val input = EditText(this).apply {
            hint = "Escribe en tu TV"; minLines = 2
            setPadding(18.dp, 14.dp, 18.dp, 14.dp)
            background = shape(Color.WHITE, 18f, border)
        }
        AlertDialog.Builder(this).setTitle("Teclado").setView(input)
            .setPositiveButton("ENVIAR") { _, _ -> remote.text(input.text.toString()) }
            .setNegativeButton("CANCELAR", null).show()
        input.requestFocus()
        input.postDelayed({
            (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
        }, 250)
    }

    private fun requestNetworkPermissionAndDiscover() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.NEARBY_WIFI_DEVICES), 77)
        else discoverTvs()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 77) discoverTvs()
    }

    private fun discoverTvs() {
        status.text = "●  Buscando en tu Wi‑Fi…"; status.setTextColor(muted)
        SamsungTvDiscovery.discover(this,
            onStatus = { msg -> runOnUiThread { status.text = "●  $msg" } },
            onDone = { tvs -> runOnUiThread {
                when {
                    tvs.isEmpty() -> { status.text = "●  No encontré el TV"; manualFallbackDialog() }
                    tvs.size == 1 -> connectTv(tvs.first())
                    else -> {
                        val labels = tvs.map { "${it.name}\n${it.model} · ${it.ip}" }.toTypedArray()
                        AlertDialog.Builder(this).setTitle("Selecciona tu Samsung TV")
                            .setItems(labels) { _, which -> connectTv(tvs[which]) }
                            .setNegativeButton("CANCELAR", null).show()
                    }
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
        val input = EditText(this).apply { hint = "IP del TV"; setText(saved); setPadding(18.dp, 10.dp, 18.dp, 10.dp) }
        AlertDialog.Builder(this).setTitle("No encontré el TV automáticamente")
            .setMessage("Verifica que el teléfono y el TV estén en la misma Wi‑Fi. Puedes reintentar o escribir la IP solo como alternativa.")
            .setView(input)
            .setPositiveButton("CONECTAR") { _, _ -> input.text.toString().trim().takeIf { it.isNotBlank() }?.let { remote.connect(it) } }
            .setNeutralButton("BUSCAR OTRA VEZ") { _, _ -> discoverTvs() }
            .setNegativeButton("CANCELAR", null).show()
    }

    private class TouchPadView(context: Context, private val send: (String) -> Unit) : View(context) {
        private var downX = 0f; private var downY = 0f
        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN -> { downX = event.x; downY = event.y; return true }
                MotionEvent.ACTION_UP -> {
                    val dx = event.x - downX; val dy = event.y - downY
                    if (abs(dx) < 35 && abs(dy) < 35) send("KEY_ENTER")
                    else if (abs(dx) > abs(dy)) send(if (dx > 0) "KEY_RIGHT" else "KEY_LEFT")
                    else send(if (dy > 0) "KEY_DOWN" else "KEY_UP")
                    performClick(); return true
                }
            }
            return true
        }
        override fun performClick(): Boolean { super.performClick(); return true }
    }
}
