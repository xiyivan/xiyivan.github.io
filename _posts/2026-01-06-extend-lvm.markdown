---
layout: post
title:  "Extending lvm"
date:   2026-01-06 13:51:00 -0500
categories: [tech]
---

Now that I have used Arch for a period of time and it has performed well, I want to allocate more space from the Windows partition to the Arch partition. The only problem is my Windows partition is located before the LVM that contains my Arch partitions.

My original plan was to create a new physical volume and add it to the LVM. However, since I had not yet stored any important documents on the system, I decided to directly increase the size of the existing volume. Here are the steps I took:

First, the most important step is to create backups. Keep recovery images for both systems on a separate drive in case anything goes wrong. Before starting any disk operations, I recommend creating a Ventoy USB drive with GParted Live, Arch Linux, and Windows installation ISOs. I also recommend saving a backup of the partition table to the same USB drive.

I used DiskGenius to decrease the Windows volume size and GParted to increase the LVM volume size. You could theoretically use GParted for both operations, but DiskGenius is known for having better support for Windows. The only issue I had in this process was that the LVM was mounted for some reason, which I didn't notice initially. Therefore, be sure to unmount all volumes using umount -a before proceeding.

After moving the LVM, we need to fix GRUB. This [guide](https://gparted.org/display-doc.php?name=help-manual&lang=C#gparted-fix-grub-boot-problem) from GParted was very useful. For Arch users, this process can be further simplified by booting into an Arch Live environment.

For Arch users with an LVM on a UEFI system, the process I used was as follows:

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