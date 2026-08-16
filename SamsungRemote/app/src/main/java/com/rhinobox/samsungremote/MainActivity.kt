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

    private val bg = Color.rgb(247, 249, 253)
    private val surface = Color.WHITE
    private val ink = Color.rgb(17, 24, 39)
    private val muted = Color.rgb(105, 114, 130)
    private val line = Color.rgb(231, 235, 242)
    private val accent = Color.rgb(86, 92, 244)
    private val accentSoft = Color.rgb(238, 240, 255)
    private val success = Color.rgb(34, 197, 94)
    private val danger = Color.rgb(245, 48, 48)

    private val Int.dp: Int get() = (this * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("samsung_remote", 0)
        remote = SamsungRemoteClient { s, ok ->
            runOnUiThread {
                status.text = "● $s"
                status.setTextColor(if (ok) success else muted)
            }
        }
        remote.attach(this)
        buildUi()
        requestNetworkPermissionAndDiscover()
    }

    private fun rounded(color: Int = surface, radius: Float = 24f, stroke: Int? = line, strokeWidth: Int = 1): GradientDrawable {
        return GradientDrawable().apply {
            cornerRadius = radius * resources.displayMetrics.density
            setColor(color)
            if (stroke != null) setStroke(strokeWidth.dp, stroke)
        }
    }

    private fun textView(text: String, size: Float = 14f, color: Int = ink, bold: Boolean = false, gravityValue: Int = Gravity.CENTER): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            gravity = gravityValue
            includeFontPadding = false
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }
    }

    private fun tapCard(
        text: String,
        key: String? = null,
        height: Int = 58,
        radius: Float = 20f,
        textSizeSp: Float = 13f,
        foreground: Int = ink,
        backgroundColor: Int = surface,
        action: (() -> Unit)? = null
    ): TextView {
        return textView(text, textSizeSp, foreground, false).apply {
            isClickable = true
            isFocusable = true
            background = rounded(backgroundColor, radius)
            elevation = 2.dp.toFloat()
            setPadding(8.dp, 8.dp, 8.dp, 8.dp)
            setOnClickListener {
                performHapticFeedback(android.view.HapticFeedbackConstants.KEYBOARD_TAP)
                if (action != null) action() else key?.let { remote.key(it) }
            }
            layoutParams = LinearLayout.LayoutParams(-1, height.dp)
        }
    }

    private fun addWeighted(row: LinearLayout, view: View, weight: Float = 1f, height: Int = 58, margin: Int = 5) {
        row.addView(view, LinearLayout.LayoutParams(0, height.dp, weight).apply {
            setMargins(margin.dp, margin.dp, margin.dp, margin.dp)
        })
    }

    private fun buildUi() {
        window.statusBarColor = bg
        window.navigationBarColor = Color.rgb(248, 250, 253)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        }

        val scroll = ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            clipToPadding = false
            overScrollMode = View.OVER_SCROLL_NEVER
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16.dp, 10.dp, 16.dp, 24.dp)
        }
        scroll.addView(root)
        setContentView(scroll)

        val header = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val menu = tapCard("☰", height = 54, radius = 18f, textSizeSp = 24f, action = { showMenuDialog() })
        header.addView(menu, LinearLayout.LayoutParams(54.dp, 54.dp))

        val titleBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        tvName = textView("Samsung TV", 20f, ink, true)
        status = textView("● Buscando TV…", 12.5f, muted)
        titleBox.addView(tvName, LinearLayout.LayoutParams(-1, 29.dp))
        titleBox.addView(status, LinearLayout.LayoutParams(-1, 21.dp))
        header.addView(titleBox, LinearLayout.LayoutParams(0, 58.dp, 1f))

        val refresh = tapCard("↻", height = 54, radius = 18f, textSizeSp = 25f, action = { discoverTvs() })
        header.addView(refresh, LinearLayout.LayoutParams(54.dp, 54.dp))
        root.addView(header)

        val tabs = LinearLayout(this).apply {
            gravity = Gravity.CENTER
            setPadding(0, 9.dp, 0, 3.dp)
        }
        val tabControl = tab("⌾  Control", true) { showControlTab() }
        val tabNav = tab("▦  Navegación", false) { showNavigationTab() }
        val tabMedia = tab("▷  Multimedia", false) { showMediaTab() }
        val tabApps = tab("▦  Apps", false) { showAppsTab() }
        val tabViews = listOf(tabControl, tabNav, tabMedia, tabApps)
        tabViews.forEachIndexed { index, v ->
            v.setOnClickListener {
                tabViews.forEachIndexed { i, t -> styleTab(t, i == index) }
                when (index) {
                    0 -> showControlTab()
                    1 -> showNavigationTab()
                    2 -> showMediaTab()
                    3 -> showAppsTab()
                }
            }
            tabs.addView(v, LinearLayout.LayoutParams(0, 44.dp, 1f).apply { setMargins(3.dp, 0, 3.dp, 0) })
        }
        root.addView(tabs)

        val power = tapCard("⏻   POWER", "KEY_POWER", height = 58, radius = 30f, textSizeSp = 16f, foreground = danger)
        root.addView(power, LinearLayout.LayoutParams(-1, 58.dp).apply { setMargins(2.dp, 9.dp, 2.dp, 10.dp) })

        val quick = LinearLayout(this).apply { gravity = Gravity.CENTER }
        quick.addView(verticalRocker("＋", "VOL", "−", "KEY_VOLUP", "KEY_VOLDOWN"), LinearLayout.LayoutParams(76.dp, 170.dp).apply { setMargins(0, 2.dp, 6.dp, 2.dp) })

        val middle = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val row1 = LinearLayout(this)
        addWeighted(row1, tapCard("⌁\nMUTE", "KEY_MUTE", height = 76, radius = 20f, textSizeSp = 13f), 1f, 76, 4)
        addWeighted(row1, tapCard("↪\nEXIT", "KEY_EXIT", height = 76, radius = 20f, textSizeSp = 13f), 1f, 76, 4)
        middle.addView(row1)
        val row2 = LinearLayout(this)
        addWeighted(row2, tapCard("⌂\nHOME", "KEY_HOME", height = 76, radius = 20f, textSizeSp = 13f), 1f, 76, 4)
        addWeighted(row2, tapCard("↶\nBACK", "KEY_RETURN", height = 76, radius = 20f, textSizeSp = 13f), 1f, 76, 4)
        middle.addView(row2)
        quick.addView(middle, LinearLayout.LayoutParams(0, 170.dp, 1f))

        quick.addView(verticalRocker("⌃", "CH", "⌄", "KEY_CHUP", "KEY_CHDOWN"), LinearLayout.LayoutParams(76.dp, 170.dp).apply { setMargins(6.dp, 2.dp, 0, 2.dp) })
        root.addView(quick)

        contentHost = FrameLayout(this)
        root.addView(contentHost, LinearLayout.LayoutParams(-1, 360.dp).apply { setMargins(0, 8.dp, 0, 6.dp) })
        showControlTab()
    }

    private fun tab(label: String, selected: Boolean, action: () -> Unit): TextView {
        return textView(label, 11f, if (selected) Color.WHITE else ink, selected).apply {
            background = rounded(if (selected) accent else surface, 22f)
            elevation = if (selected) 3.dp.toFloat() else 1.dp.toFloat()
            setOnClickListener { action() }
        }
    }

    private fun styleTab(tab: TextView, selected: Boolean) {
        tab.setTextColor(if (selected) Color.WHITE else ink)
        tab.setTypeface(tab.typeface, if (selected) Typeface.BOLD else Typeface.NORMAL)
        tab.background = rounded(if (selected) accent else surface, 22f)
        tab.elevation = if (selected) 3.dp.toFloat() else 1.dp.toFloat()
    }

    private fun verticalRocker(top: String, label: String, bottom: String, topKey: String, bottomKey: String): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            background = rounded(surface, 30f)
            elevation = 2.dp.toFloat()
            addView(tapCard(top, topKey, height = 57, radius = 0f, textSizeSp = 27f).apply { background = null; elevation = 0f }, LinearLayout.LayoutParams(-1, 57.dp))
            addView(textView(label, 12f, ink, true), LinearLayout.LayoutParams(-1, 52.dp))
            addView(tapCard(bottom, bottomKey, height = 57, radius = 0f, textSizeSp = 27f).apply { background = null; elevation = 0f }, LinearLayout.LayoutParams(-1, 57.dp))
        }
    }

    private fun showControlTab() {
        contentHost.removeAllViews()
        val pad = FrameLayout(this).apply {
            background = rounded(surface, 180f)
            elevation = 2.dp.toFloat()
        }
        fun place(v: View, w: Int, h: Int, gravity: Int, ml: Int = 0, mt: Int = 0, mr: Int = 0, mb: Int = 0) {
            pad.addView(v, FrameLayout.LayoutParams(w.dp, h.dp, gravity).apply { setMargins(ml.dp, mt.dp, mr.dp, mb.dp) })
        }

        val ok = tapCard("OK", "KEY_ENTER", height = 104, radius = 58f, textSizeSp = 18f, backgroundColor = Color.rgb(252, 253, 255)).apply {
            background = rounded(Color.rgb(252, 253, 255), 58f, accent, 1)
            elevation = 3.dp.toFloat()
        }
        place(tapCard("⌃", "KEY_UP", height = 64, radius = 0f, textSizeSp = 30f).apply { background = null; elevation = 0f }, 76, 64, Gravity.TOP or Gravity.CENTER_HORIZONTAL, mt = 14)
        place(tapCard("‹", "KEY_LEFT", height = 82, radius = 0f, textSizeSp = 42f).apply { background = null; elevation = 0f }, 74, 82, Gravity.CENTER_VERTICAL or Gravity.LEFT, ml = 12)
        place(ok, 104, 104, Gravity.CENTER)
        place(tapCard("›", "KEY_RIGHT", height = 82, radius = 0f, textSizeSp = 42f).apply { background = null; elevation = 0f }, 74, 82, Gravity.CENTER_VERTICAL or Gravity.RIGHT, mr = 12)
        place(tapCard("⌄", "KEY_DOWN", height = 64, radius = 0f, textSizeSp = 30f).apply { background = null; elevation = 0f }, 76, 64, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL, mb = 14)

        contentHost.addView(pad, FrameLayout.LayoutParams(-1, 318.dp).apply { setMargins(14.dp, 8.dp, 14.dp, 4.dp) })

        val modes = LinearLayout(this).apply { gravity = Gravity.CENTER }
        addWeighted(modes, tapCard("●\n123", action = { showNavigationTab() }, height = 54, radius = 18f, textSizeSp = 11f), 1f, 54, 4)
        addWeighted(modes, tapCard("⌨\nTECLADO", action = { keyboardDialog() }, height = 54, radius = 18f, textSizeSp = 11f), 1f, 54, 4)
        addWeighted(modes, tapCard("☝\nTOUCHPAD", action = { showTouchpadOnly() }, height = 54, radius = 18f, textSizeSp = 11f), 1f, 54, 4)
        contentHost.addView(modes, FrameLayout.LayoutParams(-1, 62.dp, Gravity.BOTTOM).apply { setMargins(38.dp, 0, 38.dp, 0) })
    }

    private fun showNavigationTab() {
        contentHost.removeAllViews()
        val wrapper = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        val nums = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        listOf(listOf("1","2","3","4","5"), listOf("6","7","8","9","0")).forEach { items ->
            val row = LinearLayout(this)
            items.forEach { n -> addWeighted(row, tapCard(n, "KEY_$n", height = 42, radius = 20f, textSizeSp = 14f), 1f, 42, 3) }
            nums.addView(row)
        }
        wrapper.addView(nums)

        val touch = TouchPadView(this) { key -> remote.key(key) }.apply {
            background = rounded(surface, 28f)
            elevation = 2.dp.toFloat()
        }
        wrapper.addView(touch, LinearLayout.LayoutParams(-1, 190.dp).apply { setMargins(4.dp, 9.dp, 4.dp, 4.dp) })
        wrapper.addView(textView("Desliza para navegar · toca para OK", 11.5f, muted), LinearLayout.LayoutParams(-1, 28.dp))

        val bottom = LinearLayout(this)
        addWeighted(bottom, tapCard("PRE-CH", "KEY_PRECH", height = 50, radius = 18f, textSizeSp = 11f), 1f, 50, 4)
        addWeighted(bottom, tapCard("CH-LIST", "KEY_CH_LIST", height = 50, radius = 18f, textSizeSp = 11f), 1f, 50, 4)
        wrapper.addView(bottom)
        contentHost.addView(wrapper, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showTouchpadOnly() {
        contentHost.removeAllViews()
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        val pad = TouchPadView(this) { key -> remote.key(key) }.apply {
            background = rounded(surface, 30f)
            elevation = 2.dp.toFloat()
        }
        box.addView(pad, LinearLayout.LayoutParams(-1, 275.dp).apply { setMargins(8.dp, 12.dp, 8.dp, 4.dp) })
        box.addView(textView("Desliza para navegar · toca para OK", 12f, muted), LinearLayout.LayoutParams(-1, 34.dp))
        contentHost.addView(box, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showMediaTab() {
        contentHost.removeAllViews()
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }

        box.addView(textView("Multimedia", 18f, ink, true), LinearLayout.LayoutParams(-1, 42.dp))
        val row = LinearLayout(this)
        addWeighted(row, tapCard("◀◀\nREW", "KEY_REWIND", height = 92, radius = 22f, textSizeSp = 13f), 1f, 92, 5)
        addWeighted(row, tapCard("▶Ⅱ\nPLAY/PAUSE", "KEY_PLAY", height = 92, radius = 22f, textSizeSp = 12f), 1f, 92, 5)
        addWeighted(row, tapCard("▶▶\nFF", "KEY_FF", height = 92, radius = 22f, textSizeSp = 13f, foreground = accent), 1f, 92, 5)
        addWeighted(row, tapCard("■\nSTOP", "KEY_STOP", height = 92, radius = 22f, textSizeSp = 13f), 1f, 92, 5)
        box.addView(row)

        val row2 = LinearLayout(this)
        addWeighted(row2, tapCard("INFO", "KEY_INFO", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(row2, tapCard("GUIDE", "KEY_GUIDE", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(row2, tapCard("MENU", "KEY_MENU", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(row2, tapCard("CH-LIST", "KEY_CH_LIST", height = 68, radius = 20f), 1f, 68, 5)
        box.addView(row2)
        contentHost.addView(box, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showAppsTab() {
        contentHost.removeAllViews()
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        box.addView(textView("Herramientas", 18f, ink, true), LinearLayout.LayoutParams(-1, 42.dp))

        val row = LinearLayout(this)
        addWeighted(row, tapCard("⌕\nSEARCH", "KEY_SEARCH", height = 92, radius = 22f, textSizeSp = 12f), 1f, 92, 5)
        addWeighted(row, tapCard("⌨\nKEYBOARD", action = { keyboardDialog() }, height = 92, radius = 22f, textSizeSp = 12f), 1f, 92, 5)
        addWeighted(row, tapCard("↪\nSOURCE", "KEY_SOURCE", height = 92, radius = 22f, textSizeSp = 12f), 1f, 92, 5)
        addWeighted(row, tapCard("▤\nE-MANUAL", "KEY_E-MANUAL", height = 92, radius = 22f, textSizeSp = 12f), 1f, 92, 5)
        box.addView(row)

        val second = LinearLayout(this)
        addWeighted(second, tapCard("INFO", "KEY_INFO", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(second, tapCard("GUIDE", "KEY_GUIDE", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(second, tapCard("MENU", "KEY_MENU", height = 68, radius = 20f), 1f, 68, 5)
        addWeighted(second, tapCard("CH-LIST", "KEY_CH_LIST", height = 68, radius = 20f), 1f, 68, 5)
        box.addView(second)
        contentHost.addView(box, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showMenuDialog() {
        val options = arrayOf("Buscar TV otra vez", "Introducir IP manualmente", "Acerca del control")
        AlertDialog.Builder(this)
            .setTitle("Samsung Remote")
            .setItems(options) { _, which ->
                when (which) {
                    0 -> discoverTvs()
                    1 -> manualFallbackDialog()
                    2 -> AlertDialog.Builder(this).setTitle("Samsung Remote").setMessage("Control remoto local para Samsung TV.\nConexión directa por Wi‑Fi.").setPositiveButton("OK", null).show()
                }
            }
            .setNegativeButton("CERRAR", null)
            .show()
    }

    private fun keyboardDialog() {
        val input = EditText(this).apply {
            hint = "Escribe en tu TV"
            minLines = 2
            setPadding(18.dp, 16.dp, 18.dp, 16.dp)
            background = rounded(Color.rgb(249, 250, 253), 16f)
        }
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
        } else {
            val saved = prefs.getString("last_ip", "") ?: ""
            if (saved.isNotBlank()) {
                status.text = "● Conectando…"
                remote.connect(saved)
            } else discoverTvs()
        }
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
        tvName.text = tv.name.ifBlank { if (tv.model.isNotBlank()) tv.model else "Samsung TV" }
        prefs.edit().putString("last_ip", tv.ip).apply()
        remote.connect(tv.ip)
    }

    private fun manualFallbackDialog() {
        val saved = prefs.getString("last_ip", "") ?: ""
        val input = EditText(this).apply {
            hint = "IP del TV"
            setText(saved)
            setPadding(18.dp, 10.dp, 18.dp, 10.dp)
        }
        AlertDialog.Builder(this)
            .setTitle("Conectar manualmente")
            .setMessage("Escribe la IP del televisor solo si la búsqueda automática no lo encuentra.")
            .setView(input)
            .setPositiveButton("CONECTAR") { _, _ ->
                val ip = input.text.toString().trim()
                if (ip.isNotBlank()) {
                    prefs.edit().putString("last_ip", ip).apply()
                    remote.connect(ip)
                }
            }
            .setNeutralButton("BUSCAR") { _, _ -> discoverTvs() }
            .setNegativeButton("CANCELAR", null)
            .show()
    }

    private class TouchPadView(context: Context, private val send: (String) -> Unit) : View(context) {
        private var downX = 0f
        private var downY = 0f

        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.x
                    downY = event.y
                    return true
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

        override fun performClick(): Boolean {
            super.performClick()
            return true
        }
    }
}
