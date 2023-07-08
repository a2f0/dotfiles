#!/bin/bash
rsync --verbose \
      --progress \
      --omit-dir-times \
      --no-perms \
      --recursive \
      --inplace \
      --delete \
      --size-only \
      --exclude=.thumbnails \
      ~/a2f0-s3-archive/data/Music/ \
      /run/user/1000/gvfs/mtp:host=Google_Pixel_6a_33011JEGR05873/Internal\ shared\ storage/Music/
