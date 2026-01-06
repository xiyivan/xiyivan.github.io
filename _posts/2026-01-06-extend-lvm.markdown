---
layout: post
title:  "Extending lvm"
date:   2026-01-06 13:51:00 -0500
categories: [tech]
---

Now that I have used arch for a period of time, and it performed well during that period, I want to migrate more space from the windows partition to the arch partition. The only problem been my windows partition located before the lvm that contains my arch partitions. 

My original plan was to create a new physical volume and add it to the lvm, but since there were no important document been stored yet, I decided to directly increase the existing volume size. Here are the steps I took:

First, and the most important part is to backup. Keep a recovery image on a separate drive for both systems in case anything went wrong. Before starting file operation, I recommend create a vortey usb with Gparted live, Arch and Windows install iso. I also recommend saving a backup of the partition table to the same usb.

I used disk genius to decrease windows volume size and GParted to increase the lvm volume size. You can theortically use GParted for both operation, but disk genius is known for having better support for windows. The only issue I had in this process was that the lvm was mounted for some reason, and I didn't notice it, so be sure to unmount all volumes using `umount -a`. 

After moving the LVM, we need to fix the GRUB. This [guide](https://gparted.org/display-doc.php?name=help-manual&lang=C#gparted-fix-grub-boot-problem) from gparted was very useful. For arch user, this process can be further simplified by booting in to arch live. 

For arch users using LVM with UEFI system, the process I used was as follow:

```
# 1.activate LVM logic volume
vgchange -ay

# 2.mount root logic volume to /mnt
mount /dev/vg_arch/root /mnt

# 3.mount the efi partition
mkdir -p /mnt/boot/efi
mount /dev/nvme0n1p1 /mnt/boot/efi

# 4.chroot into the original system
arch-chroot /mnt

# 5.re-install GRUB to ESP partition
grub-install --target=x86_64-efi --efi-directory=/boot/efi /dev/nvme0n1

# 6.regen init ramdisk
mkinitcpio -P

# 7.regen GRUB config file
grub-mkconfig -o /boot/grub/grub.cfg

# 8.exit and reboot
exit
umount -R /mnt
reboot
```