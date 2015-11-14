# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|

  # uncomment the lang you use
  config.vm.box = "http://hackathon-cdn.ele.me/hackathon-py-0.1.0.vbox"
  #config.vm.box = "http://hackathon-cdn.ele.me/hackathon-java-v0.1.0.vbox"
  #config.vm.box = "http://hackathon-cdn.ele.me/hackathon-go-v0.1.0.vbox"

  # config.vm.box_check_update = false
  config.vm.provider "virtualbox" do |vb|
    vb.name = "eleme-hackathon"
    vb.cpus = 2
    vb.memory = "1024"
  end

  config.vm.provision "shell",
    inline: "initctl emit vagrant-mounted",
    run: "always"

  config.vm.network :forwarded_port, guest: 6379, host: 6379
  config.vm.network :forwarded_port, guest: 3306, host: 3306
  config.vm.network :forwarded_port, guest: 8080, host: 8080

end
