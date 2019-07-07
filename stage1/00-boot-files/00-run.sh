#!/bin/bash -e

install -m 644 files/cmdline.txt "${ROOTFS_DIR}/boot/"
install -m 644 files/config.txt "${ROOTFS_DIR}/boot/"
install -m 644 files/bcm2708-rpi-0-w.dtb "${ROOTFS_DIR}/boot/"
install -m 644 files/mzdpi.dtbo "${ROOTFS_DIR}/boot/overlays/"
