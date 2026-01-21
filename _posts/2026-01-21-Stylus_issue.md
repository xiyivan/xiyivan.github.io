---
layout: post
title:  "Fix: Surface Pen on ROG Flow 13 (KDE Plasma Wayland)"
date:   2026-01-21 20:48:00 000
categories: [tech]
---

If you are using an ASUS ROG Flow 13 with an MPP (Microsoft Pen Protocol) stylus like the Surface Pen on KDE Plasma (Wayland), you might find that while the kernel sees the device, the cursor refuses to move.

Here is how I diagnosed and fixed the issue when my stylus was recognized as a device but wouldn't move the pointer.

---

### Step 1: Verification (The "Before" State)

Even without configuration, Linux often "sees" the hardware. I started by checking if the kernel was receiving signals.
- Command: `sudo evtest`
- Result: I selected the `ELAN9008` device. Moving the pen showed a stream of $ABS\_X$ and $ABS\_Y$ coordinates.
- What this told me: The hardware is fine. The screen digitizer is working, and the kernel driver (`hid-multitouch`) is active. The problem lies higher up.

### Step 2: Bridging the Gap with libwacom

KDE Plasma relies on a library called `libwacom` to identify tablets. If THE device isn't in its database, the "Graphics Tablet" settings page in KDE will be empty or missing features.

- The Problem: `libwacom-list-local-devices` showed the device was "not supported."
- The Fix: I created a custom tablet definition file at `/etc/libwacom/elan-9008.tablet`.
- The Data:

```
[Device]
Name=ELAN9008:00 04F3:40FD Stylus
DeviceMatch=i2c|04f3|40fd
Class=ISDV4
IntegratedIn=Display;System
Styli=@generic-with-eraser;
```

- Why this helped: This "introduced" the stylus to the system. After running `sudo libwacom-update-db`, the Graphics Tablet section finally appeared in my KDE System Settings.

### Step 3: Debugging the "Flicker" (Wayland Input)
Even with the settings page visible, the cursor would only "flicker" or appear/disappear without actually moving.
- Command: `libinput debug-events`
- Observation: This tool showed `TABLET_TOOL_AXIS` events with perfect coordinates.
- What this told me: `libinput` was correctly processing the movement, but KWin was dropping the data. 
  
### Step 4: The Final Boss – The Calibration Matrix
This was the "Aha!" moment. I checked the KDE input configuration file to see how it was mapping the pen to the pixels.
- Command: `grep -A 20 "ELAN9008" ~/.config/kcminputrc`
- The Discovery: The `CalibrationMatrix` was filled with scientific notation numbers like 1.19e-07 (effectively 0).
- The Fix: I manually edited `~/.config/kcminputrc` and reset the matrix to the Identity Matrix:
  ```
  CalibrationMatrix=1,0,0,0,1,0,0,0,1
  ```

---

### Summary
1. Check Hardware: Use evtest to ensure the kernel sees the pen.

2. Identify for UI: Create a .tablet file so libwacom and KDE recognize the device.

3. Check libinput: Ensure debug-events shows axis movement.

4. Fix the Math: Reset the CalibrationMatrix in kcminputrc to identity matrix.