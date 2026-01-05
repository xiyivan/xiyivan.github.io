---
layout: post
title:  "Running Zenless Zone Zero on Arch Linux"
date:   2026-01-02 10:27:00 -0500
categories: [tech,game]
---

Key points
- Add executable to steam
- Place the game file in the virtual C
- Perform integrity check before launching
- Ignore the error 9041-0-0
- Enjoy the game

Since I have switched my daily OS to arch, I naturally want to minimize the time I have to boot back to Windows. Obviously professional softwares like Catia or Ansys(which is buggy even on Windows) are hard to run on linux, but I could as least try and run all my games in linux. Thanks to the consant investment in compatibility from valve, all the steam titles can run smoothly without any pain. The only remaining game is ZenlessZoneZero. 

Initially I tried to run it on standard wine, but a weird error of constant relaunching hit me, and I decided to instead using proton for this mihoyo game.

The launcher installed via steam flawlessly. After putting the game file into the virtual C under `~/.local/share/Steam/steamapps/compatdata/game_id/pfx/drive_c/Program Files/miHoYo Launcher/game/`, the launcher was capable of detecting it instantaneously. Success seemed imminent.

However, the game entered a black screen after the initial logo appeared. To fix this, I ran an integrity check to prevent any file corruption from the migration. That’s when I hit a wall: the post-check download failed with error 9041-0-0, a cryptic parity-check failure.

After a few more attempt of revalidation, I decided on a last-ditch effort: bypassing the launcher entirely. By running the game executable directly from steam, the game launched perfectly, bypassing the broken launcher logic entirely.

In order to make the launching process more convenient, we can also add the application to application menu. However, the steamgameid for non-steam game can only be obtained using the "add desktop shortcut" function of steam. After creating the shortcut, we can move the file to the application menu directory using command `mv ~/Desktop/zenlesszonezero.desktop ~/.local/share/applications/`. To improve the looking, we can change the icon by editing the desktop file `nano ~/.local/share/applications/ZenlessZoneZero.desktop` and replace (or add) the entry `Icon=~/.local/share/Steam/steamapps/compatdata/3622497365/pfx/drive_c/Program Files/miHoYo Launcher/1.12.0.303/ico/nap_cn.ico`.
