source ~/working/github/dotfiles/quick
source ~/.aliases-private

# ohmyzsh
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"

# gcloud
if [ -f "$HOME/working/MacOS-Install/google-cloud-sdk/path.zsh.inc" ]; then . "$HOME/working/MacOS-Install/google-cloud-sdk/path.zsh.inc"; fi
if [ -f "$HOME/working/MacOS-Install/google-cloud-sdk/completion.zsh.inc" ]; then . "$HOME/working/MacOS-Install/google-cloud-sdk/path.zsh.inc"; fi

# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "/usr/local/opt/nvm/nvm.sh" ] && . "/usr/local/opt/nvm/nvm.sh"  # This loads nvm
[ -s "/usr/local/opt/nvm/etc/bash_completion" ] && . "/usr/local/opt/nvm/etc/bash_completion"  # This loads nvm bash_completion

# nvm automatially change version when entering a directory with .nvmrc
autoload -U add-zsh-hook
load-nvmrc() {
  local node_version="$(nvm version)"
  local nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$node_version" ]; then
      nvm use
    fi
  elif [ "$node_version" != "$(nvm version default)" ]; then
    echo "Reverting to nvm default version"
    nvm use default
  fi
}
add-zsh-hook chpwd load-nvmrc
load-nvmrc

# rbenv
if hash rbenv 2>/dev/null; then
  echo "loading rbenv..."
    eval "$(rbenv init -)"
  else
    echo "rbenv not installed"
fi

# android studio
export ANDROID_HOME=$HOME/Library/Android
export PATH=$PATH:$HOME/Library/Android/sdk/emulator
export PATH=$PATH:$HOME/Library/Android/sdk/platform-tools

# rust
export PATH="$HOME/.cargo/bin:$PATH"

# make sure some other program is not messing with the environment
if [ -e  ~/.zprofile ]; then
  echo "deleting ~/.zprofile:"
  cat ~/.zprofile
  rm -rf ~/.zprofile
  echo "done deleting ~/.zprofile.."
fi

# ohmyzsh plugins
plugins=(git)
source $ZSH/oh-my-zsh.sh

# set the locale
export LC_ALL=en_US.UTF-8
