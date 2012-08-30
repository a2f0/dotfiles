trap ctrl_c INT

function ctrl_c() {
    echo "* Trapped CTRL-C *"
}

if [ `uname` == Darwin ]; then
    echo "Darwin detected"
    PATH=$PATH:/opt/local/bin
    PATH=$PATH:/Users/dsullivan2/scripts
    PATH=$PATH:/opt/local/lib/postgresql91/bin
    PATH=$PATH:/Users/dsullivan2/Dropbox/scripts/adedit
elif [ `uname` == Linux ]; then 
    echo "Linux box detected."
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

source ~/.aliases
source ~/.aliases-private
source ~/.functions
source ~/.insanely_lazy

dirty_bash_prompt

#set vi mode
set -o vi

export IRCSERVER="irc.servercentral.net 9999 IRC-SSL"
export IRCNICK="dps"
export IRCNAME="dan sullivan"

#exempt commands that start with spaces from ~/.bash_history
export HISTCONTROL=ignorespace

if [ $TERM == xterm ]; then 
    #disable audible beep for X11
    xset -b 
        #set the mouse tracking speed to fast
    xset m 7 10
        # set the keyboard repeat rate 
    xset r rate 200 100
fi

#Enable timestamping on bash_history (type history to see timestamps)
export HISTTIMEFORMAT="%d.%m.%y %T "
