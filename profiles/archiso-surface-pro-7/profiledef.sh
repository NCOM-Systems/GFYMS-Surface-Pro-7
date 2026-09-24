#!/usr/bin/env bash

iso_name="gfyms-surface-pro-7"
iso_label="GFYMS_SP7"
iso_publisher="GFYMS Project <https://github.com/pfn000/GFYMS-Surface-Pro-7>"
iso_application="GFYMS Surface Pro 7 Arch Linux"
iso_version="2026.09"
install_dir="arch"
buildmodes=('iso')
bootmodes=('uefi-x64.systemd-boot' 'uefi-x64.grub' 'bios.syslinux.mbr')
arch="x86_64"
pacman_conf="${profile}/pacman.conf"
