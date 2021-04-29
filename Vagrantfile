Vagrant.configure("2") do |config|
  config.vbguest.auto_update = false
  config.vm.box = "archlinux/archlinux"
  config.vm.provider 'virtualbox' do |v|
    v.gui = true
    v.customize ["modifyvm", :id, "--graphicscontroller", "vmsvga"]
    v.customize ["modifyvm", :id, "--vram", "64"]
    v.customize ["modifyvm", :id, "--vrde", "off"]
  end
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook-arch-linux.yaml"
  end
end
