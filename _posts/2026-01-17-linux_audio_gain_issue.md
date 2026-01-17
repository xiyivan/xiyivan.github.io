---
layout: post
title:  "Fixing bad microphone quility in linux"
date:   2026-01-17 18:10:00 -0500
categories: [tech]
---

I recently had a Discord call with my friends and we immediately found that the quality of my internal microphone sucks. This turned out to be an issue with microphone gain, which is surprisingly difficult to source with modern software despite being a simple problem.

The reason it’s confusing is that applications like Discord control the microphone gain from their end. This keeps the volume from being loud enough to immediately identify as a gain issue, though the constant popping and high sensitivity indicate otherwise.

For anyone using ALSA, the fix is as simple as getting into alsamixer and manually changing the gain of the internal microphone.