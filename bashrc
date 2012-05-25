source ~/Dropbox/arch_x86_64_configs/aliases
source ~/Dropbox/arch_x86_64_configs/aliases-private
source ~/Dropbox/arch_x86_64_configs/functions

dirty_bash_prompt

#disable terminal beep
setterm -blength 0

export IRCSERVER="irc.servercentral.net 9999 IRC-SSL"
export IRCNICK="dps"
export IRCNAME="dan sullivan"

if [ $TERM == xterm ]; then 
	#disable audible beep for X11
	xset -b
        #set the mouse tracking speed to fast
        xset m 7 10
        # set the keyboard repeat rate 
        xset r rate 200 100
fi
