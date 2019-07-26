on_chroot << EOF
pip3 install beacontools
pip3 install beacontools[scan]
pip3 install evdev
pip3 install RPi.GPIO
pip3 install pyyaml
pip3 install pygame
setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
EOF

# Create badge directory with the important, static files
mkdir -p "${ROOTFS_DIR}/root/badge/media" "${ROOTFS_DIR}/root/badge/scripts"
# install -m 644 files/mcp.py "${ROOTFS_DIR}/root/badge/"
install -m 644 files/media/hacking.mp4 "${ROOTFS_DIR}/root/badge/media/"
install -m 644 files/media/vibe.mp4 "${ROOTFS_DIR}/root/badge/media/"
install -m 644 files/media/vibe_active.mp4 "${ROOTFS_DIR}/root/badge/media/"
install -m 644 files/media/waifu_hack.mp4 "${ROOTFS_DIR}/root/badge/media/"
install -m 755 files/mcp.py "${ROOTFS_DIR}/root/badge/"
for i in $(ls files/scripts)
do
    install -m 755 files/scripts/$i "${ROOTFS_DIR}/root/badge/scripts/"
done

# Create badge_default directory, everything in it will be copied to /badge once it's made
mkdir -p "${ROOTFS_DIR}/root/badge_default/logs" "${ROOTFS_DIR}/root/badge_default/slideshow"
install -m 644 files/config.yaml "${ROOTFS_DIR}/root/badge_default/"
install -m 644 files/media/default.mp4 "${ROOTFS_DIR}/root/badge_default/"
for i in $(ls files/slideshow)
do
    install -m 644 files/slideshow/$i "${ROOTFS_DIR}/root/badge_default/slideshow/"
done
