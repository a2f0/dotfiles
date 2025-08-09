Vagrant.configure("2") do |config|
  config.vm.box = "generic/arch"
  # https://stackoverflow.com/questions/37556968/vagrant-disable-guest-additions
  if Vagrant.has_plugin?("vagrant-vbguest")
    config.vbguest.auto_update = false
  end
  config.vm.provider 'virtualbox' do |v|
    v.gui = false
    v.customize ["modifyvm", :id, "--graphicscontroller", "vmsvga"]
    v.customize ["modifyvm", :id, "--vram", "64"]
    v.customize ["modifyvm", :id, "--vrde", "off"]
    v.customize ['modifyvm', :id, "--clipboard", "bidirectional"]
    v.customize ['modifyvm', :id, "--audio", "none"]
    v.memory = 8192
    v.cpus = 2
  end
  config.vm.provision "shell",
    inline: <<-SHELL
set -euo pipefail
# Use a reliable mirror to avoid outdated package databases
sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.bak || true
echo 'Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null

# Reinitialize pacman keyring and populate Arch keys
sudo rm -rf /etc/pacman.d/gnupg
sudo pacman-key --init
sudo pacman-key --populate archlinux

# Refresh package databases and update keyring first
sudo pacman -Syy --noconfirm
sudo pacman -S --noconfirm archlinux-keyring

# Optionally refresh keys (best-effort)
sudo pacman-key --refresh-keys || true

# Clean any stale/corrupted cached packages to avoid prompts
sudo pacman -Scc --noconfirm || true

# Full system upgrade
sudo pacman -Syu --noconfirm
SHELL
  config.vm.provision "shell",
    inline: "sudo pacman -S --noconfirm --needed python"
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook-arch-linux-vm.yaml"
  end
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook-arch-linux.yaml"
    # ansible.raw_arguments = ['-vvv']
  end
  config.vm.synced_folder ".", "/vagrant", type: "rsync"
  config.vm.provision "shell",
    inline: "sudo pacman -S --noconfirm virtualbox-guest-utils"
end
