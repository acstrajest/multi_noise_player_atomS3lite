# AtomS3 Lite Multi-Noise Player

A lightweight, high-functionality multi-noise generator for the M5Stack AtomS3 Lite (paired with Atomic SPK Base and ATOM TailBAT). It dynamically generates Pink, Brown, and White noise in real-time for pure focus and relaxation.

## Hardware Setup

* **Main Unit:** M5Stack AtomS3 Lite
* **Audio Output:** Atomic SPK Base – I2S audio module with a built-in 3.5mm headphone jack for private listening
* **Power Source:** ATOM TailBAT (Portable battery setup)

## Pin Configuration

| Function | GPIO Pin | Description |
| :--- | :--- | :--- |
| **BCLK** (Bit Clock) | GPIO 5 | I2S Audio |
| **WS** (Word Select / LRCK) | GPIO 39 | I2S Audio |
| **DATA** (Data Out) | GPIO 38 | I2S Audio |
| **Button** (Built-in) | GPIO 41 | Single / Double / Long Press Multi-Control |
| **LED** (WS2812) | GPIO 35 | Status & Mode Indicator RGB LED |

## How to Use

Control everything seamlessly using the single built-in button on the AtomS3 Lite:

* **Single Click:** Cycle through noise modes:
  * Stopped → 🩷 Pink Noise → 💙 Brown Noise → 🤍 White Noise → Stopped ...
* **Double Click:** Toggle Play / Stop instantly.
  * Stops playback immediately from any mode. If currently stopped, double-clicking starts Pink Noise playback.
* **Long Press (Hold):** Enter **Volume Adjustment Mode**.
  * While holding down the button, the volume smoothly ramps up and down. Release the button at your desired level to lock in the volume.
  * *Note: To protect your hearing, the volume automatically resets to the minimum level (`VOLUME_MIN`) whenever playback starts or the mode is switched.*

**Audio Output:**  
Plug your favorite wired earphones or headphones into the 3.5mm audio jack on the Atomic SPK Base module.

## Features

* **3 Real-time Noise Algorithms:** Dynamically calculates 16-bit mono / 16 kHz Pink, Brown, and White noise without relying on pre-recorded audio files.
* **Built-in Loudness Correction:** Applies custom equalization tailored to each noise profile, ensuring comfortable and balanced listening even at very low volumes.
* **Visual Breathing LED Effects:** The RGB LED gently pulses (breathe effect) in distinct colors corresponding to the active noise type, giving clear visual status feedback.
* **Non-blocking Seamless Volume Control:** Powered by a custom non-blocking button state machine that allows real-time volume adjustment while audio continues playing smoothly (LED lights solid yellow during adjustment).
* **Zero External Dependencies:** Built with a custom `SimpleLED` class utilizing `machine.bitstream` (no external `neopixel` library required).

## LED Status Table

| LED Display | State / Mode |
| :--- | :--- |
| 🟢 **Green (Solid)** | Stopped / Standby |
| 🩷 **Pink (Breathing)** | Playing Pink Noise |
| 💙 **Blue (Breathing)** | Playing Brown Noise |
| 🤍 **White (Breathing)** | Playing White Noise |
| 💛 **Yellow (Solid)** | Adjusting Volume (Button Held) |

## Quick Start

1. Flash **MicroPython** firmware onto your AtomS3 Lite.
2. Stack the **Atomic SPK Base** and **ATOM TailBAT** onto the AtomS3 Lite.
3. Upload the script as `main.py` to the device and run it.

---

## FAQ

**Q. How do I change the volume range or adjustment speed?**  
A. You can tweak the parameters at the top of the script:
* `VOLUME_MIN`: Minimum volume level (default: `100`)
* `VOLUME_MAX`: Maximum volume level (default: `1500`)
* `VOLUME_STEP`: Volume change rate per loop (default: `25`)

**Q. Why does the volume reset when starting playback?**  
A. It is a safety feature designed to prevent sudden loud bursts of sound when plugging in earphones, protecting your ears and headphones.

**Q. Are there specific requirements for earphones?**  
A. No special high-impedance gear is required. It is tuned to work smoothly with standard, budget-friendly wired earphones (such as standard 100-yen shop models). The built-in loudness correction maintains rich bass and smooth high frequencies on any standard pair.
