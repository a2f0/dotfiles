#!/bin/sh
#
#   Dan Sullivan
#   Universal ~/.bashrc
#   First commit Jan 22, 2013

#check in ~/.functions for cntrl_c function
trap ctrl_c INT
trap hangup HUP
trap hangup KILL

#set the umask to prevent files from being created with access
#to group members or others
umask 0077

NPM_PACKAGES="$HOME/.npm-packages"
PATH="$NPM_PACKAGES/bin:$PATH"
# Unset manpath so we can inherit from /etc/manpath via the `manpath` command
unset MANPATH
MANPATH="$NPM_PACKAGES/share/man:$(manpath)"

#Tell Node about these packages
NODE_PATH="$NPM_PACKAGES/lib/node_modules:$NODE_PATH"

if [ `uname` == Darwin ]; then
    echo "Darwin detected in bashrc"
    #PATH=$PATH:/usr/local/rvm/bin
    PATH=$PATH:/opt/local/bin
    PATH=$PATH:$HOME/scripts
    PATH=$PATH:/opt/local/lib/postgresql91/bin
    #PATH=$PATH:/Users/`whoami`/Dropbox/scripts/adedit
    #PATH=$PATH:~/Dropbox/scripts
    PATH=$PATH:/opt/local/lib/mysql5/bin/
    PATH=$PATH:/opt/mongodb/bin
    PATH=$PATH:/Applications/LibreOffice.app/Contents/MacOS/

    #stuff for perl cpan
    #don't use CPAN anymoe use perlbrew
    #export PERL_LOCAL_LIB_ROOT="$PERL_LOCAL_LIB_ROOT:/home/`whoami`/perl5";
    #export PERL_MB_OPT="--install_base /home/`whoami`/perl5";
    #export PERL_MM_OPT="INSTALL_BASE=/home/`whoami`/perl5";
    #export PERL5LIB="/home/`whoami`/perl5/lib/perl5:$PERL5LIB";
    #export PATH="/home/`whoami`/perl5/bin:$PATH";
    export JAVA_HOME=`/usr/libexec/java_home -v 1.6`
    export GOPATH=~/working/github/go
    PATH=$PATH:~/working/github/go/bin

elif [ `uname` == Linux ]; then 
    echo "Linux box detected in bashrc"
    #init volume to 20.
    amixer sset Master 67% 
    PATH=$PATH:/opt/local/scripts
    PATH=$PATH:~/.cabal/bin
    PATH=$PATH:/usr/local/heroku/bin
    #vendor perl, for perlbrew
    PATH=$PATH:/usr/bin/vendor_perl
    #disable terminal beep
    setterm -blength 0
    if [ -z "${SSH_CONNECTION}" ]; then
        if [[ $TERMCAP =~ screen ]]; then
            echo "GNU screen is running..."
        else
            echo "GNU screen is not running..."
        fi
    else
        echo "This is not an SSH session..."
    fi
    #X Desktop Group Configuration Paths
    export XDG_CONFIG_HOME=$HOME/.config
    export XDG_CACHE_HOME=$HOME/.cache
    #use the default POSIX/C locale, print only standard ASCII characters.
    export LC_ALL=C
    export JAVA_HOME=/opt/local/jdk1.7.0_45
else
    echo "Unknown platform detected..."
fi

#unset and resource all aliases
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
#set -o vi
#enable vi mode
#set +o vi

#see efnet/freenode bash shell functions in ~/functions
#export IRCSERVER="irc.servercentral.net 9999 IRC-SSL"
export IRCNICK="dps"
export IRCNAME="dan sullivan"

#Set CVS remote shell
export CVS_RSH=ssh

#exempt commands that start with spaces from ~/.bash_history
export HISTCONTROL=ignorespace

#if [[ $TERM == xterm || $TERM == "rxvt-unicode-256color" ]]; then
if [[ -z "$SSH_TTY" && `uname -a` =~ ARCH ]]; then
    #we know we are not logged in via ssh i.e. we are at the console
    echo "This looks like an xsession, running xset..."
    #disable audible beep for X11
    xset -b 
    #set the mouse tracking speed to fast
    xset m 7 10
    # set the keyboard repeat rate, karabiner 200, 10
    xset r rate 200 100
    
    #re-hash this with every load
    xrdb -load ~/.Xresources
    
    #verify settings
    #xrdb -query
else
    echo "This is an SSH session..."
fi

#Enable timestamping on bash_history (type history to see timestamps)
export HISTTIMEFORMAT="%d.%m.%y %T "

#Set the editor
export EDITOR="vim"

#wipe out old screens
screen -wipe > /dev/null
screen -list

if [ ! -d ~/.mcabber/otr ]; then
    #Mcabber is configured to automatically generate OTR keys.
    #https://github.com/dsulli99/arch_x86_64_configs/blob/master/mcabberrc
    echo "Configuring directory for mcabber OTR keys..."
    mkdir -p ~/.mcabber/otr
    chmod -R 700 ~/.mcabber
fi

#load rvm if its installed
#if [ -e ~/.rvm/scripts/rvm ]; then
#    source ~/.rvm/scripts/rvm > /dev/null
#    export PATH=$HOME/.rvm/bin:$PATH;
    :
#fi
#unload it immediately afterwards
#added this 12/30/2013 for rbenv support to dev with Rails 4.
#__rvm_unload

#load rbenv if it is installed
#if [ -d "$HOME/.rbenv/bin" ]; then
#    export PATH="$HOME/.rbenv/bin:$PATH"
#    eval "$(rbenv init -)"
#    :
#fi
loadrbenv

if [ -e ~/perl5/perlbrew/etc/bashrc ]; then
  echo "initializing perlbrew"
  source ~/perl5/perlbrew/etc/bashrc
fi

if [ -e ~/.dotfiles-devopsrockstars/init ]; then
  source ~/.dotfiles-devopsrockstars/init
fi

if [ -e ~/working/github/arch_x86_64_configs/quick ]; then
  source ~/working/github/arch_x86_64_configs/quick
fi

eval $(ssh-agent)
ssh-add
