#!/bin/sh

xset r rate 200 100

if lsusb | grep -q "Metadot Das Keyboard"; then
    echo "Das Keyboard detected, running xmodmap"
    script_path=$(realpath -- "$0") || exit 1
    xmodmap "$(dirname -- "$script_path")/../Xmodmap-Das-Keyboard-Mac"
else
    echo "Das Keyboard not found, skipping xmodmap"
fi
