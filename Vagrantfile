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
    inline: "sudo pacman-key --init && sudo pacman-key --populate archlinux"

  config.vm.provision "shell",
    inline: "vagrant plugin install vagrant-vbguest"

  # Manual provisioner
  config.vm.provision "shell",
    sudo pacman -S --noconfirm gcc make dkms linux-headers

  # vbguest provisioner with fallback
  if Vagrant.has_plugin?("vagrant-vbguest")
    config.vbguest.auto_update = true
    config.vbguest.no_remote = false
    config.vbguest.installer_options = { force: true } # Force update if needed
    config.vm.provision :vbguest
  else
    puts "ERROR: vagrant-vbguest plugin is required. Install it with: vagrant plugin install vagrant-vbguest"
    exit 1
  end


  # config.vm.provision "shell",
  #   inline: "sudo pacman -S --noconfirm python"
  # config.vm.provision "ansible" do |ansible|
  #     ansible.playbook = "playbook-arch-linux-vm.yaml"
  # end
  # config.vm.provision "ansible" do |ansible|
  #     ansible.playbook = "playbook-arch-linux.yaml"
  #     ansible.raw_arguments = ['-vvv']
  # end
  # config.vm.synced_folder ".", "/vagrant", type: "rsync"
end
