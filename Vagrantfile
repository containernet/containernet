VAGRANT_COMMAND = ARGV[0]
downloaded = false
Vagrant.configure(2) do |config|
    config.vm.box = "ubuntu/xenial64"
    config.ssh.username = 'root'
    if VAGRANT_COMMAND == "provision" || VAGRANT_COMMAND == "up"
      config.ssh.username = 'vagrant'
    end
    config.ssh.insert_key = 'false'
    config.vm.provider "virtualbox" do |vb|
        vb.customize [ "modifyvm", :id, "--uartmode1", "disconnected" ]
        vb.memory = "1024"
    end
    config.trigger.before :provision do |trigger|
        if !Dir.exists?('ansible')
            `wget https://raw.githubusercontent.com/containernet/containernet/master/ansible/install_vagrant.yml -P ansible -v`
            `wget https://raw.githubusercontent.com/containernet/containernet/master/ansible/tasks.yml -P ansible -v`
            downloaded = true
        end
    end
    config.trigger.after :provision do |trigger|
        if downloaded
            trigger.run = {inline: "rm -rf ansible"}
        end
    end
    config.vm.provision "ansible_local" do |a|
        a.playbook = "ansible/install_vagrant.yml"
    end
end