package com.rhinobox.samsungremote

import android.widget.EditText

var EditText.singleLine: Boolean
    get() = maxLines == 1
    set(value) {
        setSingleLine(value)
    }
