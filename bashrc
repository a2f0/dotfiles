#!/bin/sh

trap ctrl_c INT

if [ `uname` == Darwin ]; then
    echo "Darwin detected"
    PATH=$PATH:/usr/local/rvm/bin
    PATH=$PATH:/opt/local/bin
    PATH=$PATH:/Users/dsullivan2/scripts
    PATH=$PATH:/opt/local/lib/postgresql91/bin
    #PATH=$PATH:/Users/dsullivan2/Dropbox/scripts/adedit
    #PATH=$PATH:~/Dropbox/scripts
    PATH=$PATH:/opt/local/lib/mysql5/bin/
elif [ `uname` == Linux ]; then 
    echo "Linux box detected."
    PATH=$PATH:~/.gem/ruby/1.9.1/bin
    PATH=$PATH:/opt/local/scripts
    #disable terminal beep
    setterm -blength 0
    if [ -z "${SSH_CONNECTION}" ]; then
        if [[ $TERMCAP =~ screen ]]; then
            echo "GNU screen is running."
        else
            echo "GNU screen is not running"
        fi
    else
        echo "This is an SSH session."
    fi

else
    echo "Unknown platform detected."
fi

#unset all aliases
unalias -a
source ~/.aliases
source ~/.aliases-private

#unset all functions
for function in `declare -F | awk '{ print $3 }' `; do unset $function; done
source ~/.functions
source ~/.functions-private

#call my bash_prompt funcion
bash_prompt

#set vi mode
set -o vi

export IRCSERVER="irc.servercentral.net 9999 IRC-SSL"
export IRCNICK="dps"
export IRCNAME="dan sullivan"

#exempt commands that start with spaces from ~/.bash_history
export HISTCONTROL=ignorespace

if [[ $TERM == xterm || $TERM == "rxvt-unicode-256color" ]]; then
    #disable audible beep for X11
    xset -b 
        #set the mouse tracking speed to fast
    xset m 7 10
        # set the keyboard repeat rate 
    xset r rate 200 100
    
    #re-hash this with every load
    xrdb -load ~/.Xresources
    
    #verify settings
    xrdb -query
fi

#Enable timestamping on bash_history (type history to see timestamps)
export HISTTIMEFORMAT="%d.%m.%y %T "

#Set the editor
export EDITOR="vim"

#wipe out old screens
screen -wipe > /dev/null
screen -list
