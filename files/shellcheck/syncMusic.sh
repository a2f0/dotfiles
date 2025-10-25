#!/bin/bash
# https://github.com/jb2170/better-adb-sync

if ! command -v adbsync &> /dev/null; then
    echo "Error: adbsync is not installed."
    echo ""
    echo "To install adbsync:"
    echo "  pip3 install BetterADBSync"
    echo ""
    exit 1
fi

time adbsync --delete push ~/a2f0-s3-archive/data/Music /sdcard/Music
