#!/bin/sh

xset r rate 200 100

if lsusb | grep -q "Metadot Das Keyboard"; then
    echo "Das Keyboard detected, running xmodmap"
    xmodmap ~/dotfiles/files/Xmodmap-Das-Keyboard-Mac
else
    echo "Das Keyboard not found, skipping xmodmap"
fi
