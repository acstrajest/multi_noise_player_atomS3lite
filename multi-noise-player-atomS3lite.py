import os
import struct
import time
import machine
from machine import I2S, Pin

# ==========================================
# Configuration
# ==========================================
BCLK_PIN = 5   # Bit Clock
DATA_PIN = 38  # Data Out
WS_PIN = 39    # LRCK (Word Select)
BTN_PIN = 41   # AtomS3 Lite built-in button
LED_PIN = 35   # AtomS3 Lite built-in RGB LED pin

VOLUME_MIN = 100
VOLUME_MAX = 1500
VOLUME_STEP = 25 # Volume change per loop (approx. 128ms). Takes ~7s to change by 1400.

# ==========================================
# Custom LED Controller
# ==========================================
class SimpleLED:
    def __init__(self, pin_num):
        self.pin = Pin(pin_num, Pin.OUT)
        self.buf = bytearray(3)
        
    def set_color(self, r, g, b, brightness=1.0):
        # WS2812 expects data in Green -> Red -> Blue (GRB) order
        self.buf[0] = int(g * brightness)
        self.buf[1] = int(r * brightness)
        self.buf[2] = int(b * brightness)
        machine.bitstream(self.pin, 0, (400, 850, 800, 450), self.buf)

# ==========================================
# Non-blocking Button Handler
# ==========================================
class ButtonHandler:
    def __init__(self, pin_num):
        self.pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self.state = 0
        self.press_time = 0
        self.release_time = 0
        self.long_press_triggered = False
        
    def update(self):
        now = time.ticks_ms()
        val = self.pin.value()
        event = None
        
        if val == 0: # Pressed
            if self.state == 0: # Just pressed
                self.press_time = now
                self.state = 1
                self.long_press_triggered = False
            elif self.state == 1: # Holding
                if not self.long_press_triggered and time.ticks_diff(now, self.press_time) > 1000:
                    self.long_press_triggered = True
                    event = 'LONG'
                elif self.long_press_triggered:
                    event = 'HOLDING'
            elif self.state == 2: # Second press (Double click detected early)
                self.state = 3
        else: # Released
            if self.state == 1:
                self.release_time = now
                if not self.long_press_triggered:
                    self.state = 2 # Wait to see if it's a double click
                else:
                    self.state = 0 # End of long press
            elif self.state == 2:
                if time.ticks_diff(now, self.release_time) > 250: # Timeout -> Single click
                    self.state = 0
                    event = 'SINGLE'
            elif self.state == 3: # Released after double click
                self.state = 0
                event = 'DOUBLE'
                
        return event

# ==========================================
# Initialize I2S, Button, and LED
# ==========================================
audio_out = I2S(
    0,
    sck=Pin(BCLK_PIN),
    ws=Pin(WS_PIN),
    sd=Pin(DATA_PIN),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=16000,
    ibuf=8192
)

btn = ButtonHandler(BTN_PIN)
led = SimpleLED(LED_PIN)

# LED color definitions (R, G, B)
COLOR_STOP = (0, 5, 0)      # Green (Dimmed)
COLOR_PINK = (10, 0, 5)     # Pink
COLOR_BROWN = (0, 0, 10)    # Blue (Changed from Yellow to distinguish from White)
COLOR_WHITE = (7, 7, 7)     # White
COLOR_VOL = (10, 10, 0)     # Yellow (Volume adjustment mode)

# Playback States
STATE_STOP = 0
STATE_PINK = 1
STATE_BROWN = 2
STATE_WHITE = 3

current_state = STATE_STOP
current_volume = VOLUME_MIN
vol_direction = 1

led.set_color(*COLOR_STOP)

CHUNK_SAMPLES = 2048
CHUNK_BYTES = CHUNK_SAMPLES * 2
noise_buf = bytearray(CHUNK_BYTES)

# States for filters
pink_state = [0, 0, 0, 0, 0, 0, 0]
brown_state = [0]
white_state = [0]

# ==========================================
# Noise Generators (Loudness applied by default)
# ==========================================

def generate_pink_noise(raw_bytes, out_buf, vol, state):
    _b0, _b1, _b2, _b3, _b4, _b5, _b6 = state
    _pack_into = struct.pack_into
    
    for i in range(len(raw_bytes)):
        white = raw_bytes[i] - 128
        
        _b0 = (32731 * _b0 + 1819 * white) >> 15
        _b1 = (32549 * _b1 + 2460 * white) >> 15
        _b2 = (31752 * _b2 + 5041 * white) >> 15
        _b3 = (28393 * _b3 + 10174 * white) >> 15
        _b4 = (18022 * _b4 + 17464 * white) >> 15
        _b5 = (-24956 * _b5 - 554 * white) >> 15
        
        # Loudness correction: Boost low (_b0, _b1), attenuate mid, boost high (_b6, white)
        out = ((_b0 + _b1) * 5) + ((_b2 + _b3 + _b4 + _b5) >> 1) + (_b6 * 3) + (((white * 17570) >> 15) * 3)
            
        _b6 = (white * 3798) >> 15
        
        out = (out * vol) >> 9
        
        if out > 32767: out = 32767
        elif out < -32768: out = -32768
        
        _pack_into('<h', out_buf, i * 2, out)
        
    state[0] = _b0; state[1] = _b1; state[2] = _b2
    state[3] = _b3; state[4] = _b4; state[5] = _b5; state[6] = _b6

def generate_brown_noise(raw_bytes, out_buf, vol, state):
    last_out = state[0]
    _pack_into = struct.pack_into
    
    for i in range(len(raw_bytes)):
        white = raw_bytes[i] - 128
        # Stronger low-pass filter to limit treble and emphasize bass
        last_out = (last_out * 63 + white * 64) >> 6
        
        # Loudness correction: Boost bass only, no treble added
        out = last_out * 2
            
        # Scale down overall volume
        out = (out * vol) >> 8
        
        if out > 32767: out = 32767
        elif out < -32768: out = -32768
        
        _pack_into('<h', out_buf, i * 2, out)
        
    state[0] = last_out

def generate_white_noise(raw_bytes, out_buf, vol, state):
    _pack_into = struct.pack_into
    last_low = state[0]
    
    for i in range(len(raw_bytes)):
        white = raw_bytes[i] - 128
        
        # Light low-pass filter to tame harsh treble
        last_low = (last_low * 3 + white * 4) >> 2
        
        # Loudness correction: Emphasize bass while keeping overall amplitude (no boost) to prevent excessive perceived loudness
        out = last_low
            
        # Overall volume scaling for white noise
        out = (out * vol) >> 6
        
        if out > 32767: out = 32767
        elif out < -32768: out = -32768
        
        _pack_into('<h', out_buf, i * 2, out)
        
    state[0] = last_low

# ==========================================
# Main Loop
# ==========================================
_urandom = os.urandom
print("Ready: Multi-Noise Player Started")

while True:
    # 1. Handle Button Events
    event = btn.update()
    
    if event == 'SINGLE':
        if current_state == STATE_STOP:
            current_state = STATE_PINK
            current_volume = VOLUME_MIN
            print("Playing: Pink Noise (Vol:", current_volume, ")")
        elif current_state == STATE_PINK:
            current_state = STATE_BROWN
            current_volume = VOLUME_MIN
            print("Playing: Brown Noise (Vol:", current_volume, ")")
        elif current_state == STATE_BROWN:
            current_state = STATE_WHITE
            current_volume = VOLUME_MIN
            print("Playing: White Noise (Vol:", current_volume, ")")
        elif current_state == STATE_WHITE:
            current_state = STATE_STOP
            print("Stopped")
            
    elif event == 'DOUBLE':
        if current_state == STATE_STOP:
            current_state = STATE_PINK
            current_volume = VOLUME_MIN
            print("Playing: Pink Noise (Double Click)")
        else:
            current_state = STATE_STOP
            print("Stopped (Double Click)")
            
    elif event == 'HOLDING':
        if current_state != STATE_STOP:
            # Adjust volume up and down while holding
            current_volume += VOLUME_STEP * vol_direction
            if current_volume >= VOLUME_MAX:
                current_volume = VOLUME_MAX
                vol_direction = -1
            elif current_volume <= VOLUME_MIN:
                current_volume = VOLUME_MIN
                vol_direction = 1
                
    elif event == 'LONG':
        # Reset volume change direction to 'up' on long press start
        vol_direction = 1
            
    # 2. Handle LED Updates (Breathing Effect)
    brightness = 1.0
    if current_state != STATE_STOP:
        # Breathing period: 2000ms
        t = time.ticks_ms() % 2000
        if t < 1000:
            brightness = 0.2 + 0.8 * (t / 1000.0)
        else:
            brightness = 1.0 - 0.8 * ((t - 1000) / 1000.0)
            
    if event == 'HOLDING' or event == 'LONG':
        led.set_color(*COLOR_VOL, 1.0) # Yellow LED while adjusting volume
    else:
        if current_state == STATE_STOP:
            led.set_color(*COLOR_STOP, 1.0)
        elif current_state == STATE_PINK:
            led.set_color(*COLOR_PINK, brightness)
        elif current_state == STATE_BROWN:
            led.set_color(*COLOR_BROWN, brightness)
        elif current_state == STATE_WHITE:
            led.set_color(*COLOR_WHITE, brightness)
        
    # 3. Handle Audio Generation and Output
    if current_state != STATE_STOP:
        raw = _urandom(CHUNK_SAMPLES)
        if current_state == STATE_PINK:
            generate_pink_noise(raw, noise_buf, current_volume, pink_state)
        elif current_state == STATE_BROWN:
            generate_brown_noise(raw, noise_buf, current_volume, brown_state)
        elif current_state == STATE_WHITE:
            generate_white_noise(raw, noise_buf, current_volume, white_state)
            
        audio_out.write(noise_buf)
    else:
        # Prevent busy loop freezing watchdog when stopped
        time.sleep_ms(10)