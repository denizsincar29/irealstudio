"""
commands.py – Menu command IDs, recording mode constants, and the wxPython
key-code → symbolic-name map used by the keyboard event handlers.
"""
import wx

# ---------------------------------------------------------------------------
# Menu command IDs (used as wx.MenuItem IDs for direct EVT_MENU dispatch)
# ---------------------------------------------------------------------------
_CMD_FILE_SAVE      = 1001
_CMD_FILE_SAVE_AS   = 1003
_CMD_FILE_OPEN      = 1004
_CMD_FILE_EXPORT    = 1002
_CMD_FILE_QR        = 1005
_CMD_FILE_QUIT      = 1006
_CMD_FILE_NEW       = 1007
_CMD_MIDI_REFRESH     = 2001
_CMD_MIDI_NONE        = 2002   # placeholder shown when no devices are present
_CMD_MIDI_OUT_REFRESH = 2003
_CMD_MIDI_OUT_NONE    = 2004
_CMD_SOUND_OUT_REFRESH  = 2005
_CMD_SOUND_OUT_NONE     = 2006
_CMD_SOUND_OUT_DEFAULT  = 2007  # "System default" audio device
_CMD_SETTINGS_PROJECT   = 3008  # "Project Settings…" (all-in-one dialog)
_CMD_SETTINGS_UPDATE    = 3009  # "Check for Updates…"
_LANG_BASE              = 3100  # IDs 3100..3199 → language indices 0..99
_LANGUAGES              = [('en', 'English'), ('ru', 'Русский')]
_CMD_EDIT_UNDO          = 4001
_CMD_EDIT_REDO          = 4002
_CMD_EDIT_CUT           = 4003
_CMD_EDIT_COPY          = 4004
_CMD_EDIT_PASTE         = 4005
_CMD_INSERT_CHORD       = 5001
_CMD_INSERT_SM_A        = 5010
_CMD_INSERT_SM_B        = 5011
_CMD_INSERT_SM_C        = 5012
_CMD_INSERT_SM_D        = 5013
_CMD_INSERT_SM_V        = 5014
_CMD_INSERT_SM_I        = 5015
_CMD_INSERT_SM_S        = 5016
_CMD_INSERT_SM_Q        = 5017
_CMD_INSERT_SM_F        = 5018
_CMD_INSERT_VOLTA       = 5020
_CMD_INSERT_NC          = 5021
_CMD_INSERT_BASS        = 5023
_CMD_RECORD_START             = 6001
_CMD_RECORD_PLAY              = 6002
_CMD_RECORD_STOP              = 6003
_CMD_RECORD_MODE_OVERDUB      = 6010
_CMD_RECORD_MODE_OVERWRITE    = 6011
_CMD_RECORD_OVERWRITE_WHOLE   = 6012
_CMD_HELP_SHORTCUTS     = 7001
_CMD_HELP_ABOUT         = 7002
_MIDI_DEVICE_BASE      = 2100  # IDs 2100..2199 → MIDI input device indices 0..99
_MIDI_OUT_DEVICE_BASE  = 2200  # IDs 2200..2299 → MIDI output device indices 0..99
_SOUND_OUT_DEVICE_BASE = 2300  # IDs 2300..2399 → audio output device indices 0..99

# Recording modes
RECORDING_MODE_OVERDUB    = 'overdub'
RECORDING_MODE_OVERWRITE  = 'overwrite'

# Maximum undo levels
_UNDO_MAX = 50

# ---------------------------------------------------------------------------
# wxPython key-code → symbolic-name map (used by both keydown and keyup)
# ---------------------------------------------------------------------------
_WX_KEY_SYM: dict[int, str] = {
    wx.WXK_LEFT:    'left',
    wx.WXK_RIGHT:   'right',
    wx.WXK_HOME:    'home',
    wx.WXK_END:     'end',
    wx.WXK_ESCAPE:  'escape',
    wx.WXK_SPACE:   'space',
    wx.WXK_DELETE:  'delete',
    wx.WXK_BACK:    'backspace',
    ord('/'):       'slash',
}
