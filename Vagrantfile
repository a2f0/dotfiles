Vagrant.configure("2") do |config|
  config.vbguest.auto_update = false
  config.vm.box = "generic/arch"
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
    inline: "sudo pacman -Sy archlinux-keyring --noconfirm && sudo rm -r /etc/pacman.d/gnupg &&sudo pacman-key --init && sudo pacman-key --populate archlinux && sudo pacman-key --refresh-keys"

  config.vm.provision "shell",
    inline: "sudo pacman -S --noconfirm python"
  config.vm.provision "ansible" do |ansible|
      ansible.playbook = "playbook-arch-linux-vm.yaml"
  end
  config.vm.provision "ansible" do |ansible|
      ansible.playbook = "playbook-arch-linux.yaml"
      ansible.raw_arguments = ['-vvv']
  end
  config.vm.synced_folder ".", "/vagrant", type: "rsync"
end
