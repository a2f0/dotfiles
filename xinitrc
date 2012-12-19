xset -dpms
xset s off
xsetroot -cursor_name -left_ptr
#set the audible beep for X11
xset -b
#set the mouse tracking speed to fast
xset m 7 10
#set the keyboard delay and repeat rate
xset r rate 200 100

#this configuration block is for running gnome-keyring without GNOME
# Start a D-Bus session
source /etc/X11/xinit/xinitrc.d/30-dbus
# Start GNOME Keyring
eval $(/usr/bin/gnome-keyring-daemon --start --components=gpg,pkcs11,secrets,ssh)
# You probably need to do this too:
export SSH_AUTH_SOCK
export GPG_AGENT_INFO
export GNOME_KEYRING_CONTROL
export GNOME_KEYRING_PID

#start xmonad
exec xmonad
