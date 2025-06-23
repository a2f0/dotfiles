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
    inline: "sudo pacman -Syy archlinux-keyring --noconfirm"
  config.vm.provision "shell",
    inline: "sudo pacman -S --noconfirm python"
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook-arch-linux-vm.yaml"
  end
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook-arch-linux.yaml"
    # ansible.raw_arguments = ['-vvv']
  end
  config.vm.synced_folder ".", "/vagrant", type: "rsync"
end
