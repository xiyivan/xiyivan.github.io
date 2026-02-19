---
layout: post
title:  "Abnormal dGPU Power Consumption"
date:   2026-02-19 22:34:25 0000
categories: [tech]
---

I disabled my dGPU because of its incompatibility with Kwin compositor. However, I found the device still shows up in pci devices occasionally, and consuming a lot of power.

After a bit of investigation, I found although the dGPU is not waked during a reboot, bios power it up during waking up from suspension, and makes it stuck at D0. 

The stuck was caused by the power control switched to on after the reboot. Therefore, this problem can be solved by writing a script than automatically set the power control back to auto after suspension. This can be down using a simple bash program. 