xset -dpms
xset s off
xsetroot -cursor_name -left_ptr
#set the audible beep for X11
xset -b
#set the mouse tracking speed to fast
xset m 7 10
#set the keyboard delay and repeat rate
xset r rate 200 100
exec xmonad
