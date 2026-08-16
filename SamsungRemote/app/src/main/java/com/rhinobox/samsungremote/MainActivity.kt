package com.rhinobox.samsungremote

import android.app.*
import android.os.Bundle
import android.graphics.Color
import android.graphics.Typeface
import android.view.*
import android.view.inputmethod.InputMethodManager
import android.content.Context
import android.widget.*
import android.graphics.drawable.GradientDrawable

class MainActivity : Activity() {
    private lateinit var remote: SamsungRemoteClient
    private lateinit var status: TextView
    private lateinit var prefs: android.content.SharedPreferences
    private val bg = Color.rgb(8,16,25)
    private val panel = Color.rgb(25,37,49)
    private val accent = Color.rgb(70,140,255)

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        prefs = getSharedPreferences("samsung_remote", 0)
        remote = SamsungRemoteClient { s, ok -> runOnUiThread { status.text = "● $s"; status.setTextColor(if(ok) Color.rgb(70,220,120) else Color.LTGRAY) } }
        remote.attach(this)
        showRemote()
        prefs.getString("last_ip", null)?.let { remote.connect(it) }
    }

    private fun tv(text:String, size:Float=14f) = TextView(this).apply { this.text=text; textSize=size; setTextColor(Color.WHITE); gravity=Gravity.CENTER; setPadding(8,8,8,8) }
    private fun round(v:View, radius:Float=24f, color:Int=panel) { v.background=GradientDrawable().apply { cornerRadius=radius; setColor(color) } }
    private fun button(label:String, key:String?=null, action:(()->Unit)?=null):Button = Button(this).apply {
        text=label; textSize=13f; setTextColor(Color.WHITE); isAllCaps=false; round(this,28f)
        setOnClickListener { if(action!=null) action() else if(key!=null) remote.key(key) }
    }
    private fun add(row:LinearLayout, v:View, w:Float=1f, h:Int=76) { row.addView(v, LinearLayout.LayoutParams(0,h.dp,w).apply { setMargins(5.dp,5.dp,5.dp,5.dp) }) }
    private val Int.dp:Int get()=(this*resources.displayMetrics.density).toInt()

    private fun showRemote() {
        val scroll=ScrollView(this).apply { setBackgroundColor(bg) }
        val root=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(14.dp,12.dp,14.dp,22.dp) }
        scroll.addView(root); setContentView(scroll)
        val header=LinearLayout(this).apply { gravity=Gravity.CENTER_VERTICAL }
        val title=tv("Samsung TV",21f).apply { setTypeface(null,Typeface.BOLD) }
        status=tv("● Sin conexión",12f)
        val headText=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; addView(title); addView(status) }
        header.addView(button("☰"){ connectionDialog() }, LinearLayout.LayoutParams(64.dp,64.dp))
        header.addView(headText,LinearLayout.LayoutParams(0,80.dp,1f))
        header.addView(button("⚙"){ connectionDialog() }, LinearLayout.LayoutParams(64.dp,64.dp)); root.addView(header)
        root.addView(button("⏻  POWER","KEY_POWER").apply { setTextColor(Color.rgb(255,70,70)) }, LinearLayout.LayoutParams(-1,62.dp))

        val top=LinearLayout(this)
        val vol=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; addView(button("＋\nVOL","KEY_VOLUP"),LinearLayout.LayoutParams(-1,92.dp)); addView(button("−","KEY_VOLDOWN"),LinearLayout.LayoutParams(-1,92.dp)) }
        val mid=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }
        listOf("MUTE" to "KEY_MUTE","EXIT" to "KEY_EXIT","HOME" to "KEY_HOME","BACK" to "KEY_RETURN").chunked(2).forEach { pair ->
            val r=LinearLayout(this); pair.forEach { (l,k)->add(r,button(l,k),1f,82) }; mid.addView(r)
        }
        val ch=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; addView(button("⌃\nCH","KEY_CHUP"),LinearLayout.LayoutParams(-1,92.dp)); addView(button("⌄","KEY_CHDOWN"),LinearLayout.LayoutParams(-1,92.dp)) }
        top.addView(vol,LinearLayout.LayoutParams(82.dp,-2)); top.addView(mid,LinearLayout.LayoutParams(0,-2,1f)); top.addView(ch,LinearLayout.LayoutParams(82.dp,-2)); root.addView(top)

        val nav=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(10.dp,10.dp,10.dp,10.dp); round(this,140f) }
        val nr1=LinearLayout(this); add(nr1,button("⌃","KEY_UP")); nav.addView(nr1)
        val nr2=LinearLayout(this); add(nr2,button("‹","KEY_LEFT")); add(nr2,button("OK","KEY_ENTER")); add(nr2,button("›","KEY_RIGHT")); nav.addView(nr2)
        val nr3=LinearLayout(this); add(nr3,button("⌄","KEY_DOWN")); nav.addView(nr3); root.addView(nav)

        val tabs=LinearLayout(this); add(tabs,button("◉\nDIRECCIONAL"){ }); add(tabs,button("▦\nTOUCHPAD"){ showTouchpad(root) }); add(tabs,button("123"){ showNumbers(root) }); root.addView(tabs)
        showNumbers(root)

        val tools=LinearLayout(this); add(tools,button("SEARCH","KEY_SEARCH")); add(tools,button("KEYBOARD"){ keyboardDialog() }); add(tools,button("SOURCE","KEY_SOURCE")); add(tools,button("E-MANUAL","KEY_E-MANUAL")); root.addView(tools)
        val media=LinearLayout(this); add(media,button("⏮","KEY_REWIND")); add(media,button("▶Ⅱ","KEY_PLAY")); add(media,button("⏭","KEY_FF")); add(media,button("■","KEY_STOP")); root.addView(media)
        val more=LinearLayout(this); add(more,button("INFO","KEY_INFO")); add(more,button("GUIDE","KEY_GUIDE")); add(more,button("MENU","KEY_MENU")); add(more,button("APPS","KEY_HOME")); root.addView(more)
    }

    private fun showNumbers(root:LinearLayout) {
        val box=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; tag="dynamic" }
        (1..9).chunked(3).forEach { nums -> val r=LinearLayout(this); nums.forEach { n->add(r,button(n.toString(),"KEY_$n"),1f,64) }; box.addView(r) }
        val last=LinearLayout(this); add(last,button("PRE-CH","KEY_PRECH")); add(last,button("0","KEY_0")); add(last,button("CH-LIST","KEY_CH_LIST")); box.addView(last); root.addView(box)
    }

    private fun showTouchpad(root:LinearLayout) {
        Toast.makeText(this,"Usa el panel direccional para navegación precisa",Toast.LENGTH_SHORT).show()
    }

    private fun connectionDialog() {
        val input=EditText(this).apply { hint="IP del TV (ej. 192.168.1.50)"; setText(prefs.getString("last_ip","")); inputType=android.text.InputType.TYPE_CLASS_PHONE }
        AlertDialog.Builder(this).setTitle("Conectar Samsung TV").setMessage("El teléfono y el TV deben estar en la misma Wi‑Fi. La primera vez, acepta el permiso que aparecerá en la pantalla del televisor.").setView(input)
            .setPositiveButton("CONECTAR") { _,_-> val ip=input.text.toString().trim(); prefs.edit().putString("last_ip",ip).apply(); remote.connect(ip) }
            .setNegativeButton("CANCELAR",null).show()
    }

    private fun keyboardDialog() {
        val input=EditText(this).apply { hint="Escribe texto para enviar al TV"; minLines=2 }
        AlertDialog.Builder(this).setTitle("Teclado del TV").setView(input).setPositiveButton("ENVIAR") { _,_-> remote.text(input.text.toString()) }.setNegativeButton("CANCELAR",null).show()
        input.requestFocus(); input.postDelayed({ (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input,InputMethodManager.SHOW_IMPLICIT) },250)
    }
}
