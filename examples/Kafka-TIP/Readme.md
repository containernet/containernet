Description to be added

To run: 

Inside containernet-TIP:
sudo ansible-playbook -i "localhost -c local ansible/install.yml

 Inside containernet-TIP/examples/Kafka-TIP:
sudo docker build -f Dockerfile.consumer -t kafka-consumer .
sudo docker build -f Dockerfile.producer -t kafka-producer .

Run the demo app:
sudo python3 demo.py

Remove containers:
sudo docker rm mn.broker mn.zookeeper mn.consumer mn.producer

Clean topo:
sudo mn -c

OVS error:
sudo apt-get install openvswitch-testcontroller
sudo cp /usr/bin/ovs-testcontroller /usr/bin/ovs-controller