from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel
from time import sleep

setLogLevel('info')

net = Containernet(controller=Controller)
net.addController('c0')

info('*** Adding Zookeeper\n')
zookeeper = net.addDocker('zookeeper', ip='10.0.0.251',
                       dimage="confluentinc/cp-zookeeper:7.0.1",
                       environment={"ZOOKEEPER_CLIENT_PORT": 2181,
                                    "ZOOKEEPER_TICK_TIME": 2000},
                       ports=[2181],
                       port_bindings={2181:2181})

info('*** Adding Kafka broker\n')
broker = net.addDocker('broker',ip='10.0.0.252',
                       dimage="confluentinc/cp-kafka:7.0.1",
                       environment={"KAFKA_BROKER_ID": 1,
                                    "KAFKA_ZOOKEEPER_CONNECT": 'zookeeper:2181',
                                    "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT,PLAINTEXT_INTERNAL:PLAINTEXT",
                                    "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://broker:29092",
                                    "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": 1,
                                    "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": 1,
                                    "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": 1},
                       ports=[9092],
                       port_bindings={9092:9092})



info('*** Adding producer and consumer\n')
consumer = net.addDocker('consumer', ip='10.0.0.253',
                         dimage="kafka-consumer")
producer = net.addDocker('producer', ip='10.0.0.254',
                         dimage="kafka-producer")


info('*** Setup network\n')
s1 = net.addSwitch('s1')
s2 = net.addSwitch('s2')
net.addLink(zookeeper, s1)
net.addLink(broker, s1)
net.addLink(broker, s2)
net.addLink(consumer, s2)
net.addLink(producer, s2)

net.start()

info('*** Starting to execute commands\n')

broker.start()
sleep(5)

info('Execute: consumer.cmd("python consumer.py")\n')
info(consumer.cmd("python consumer.py") + "\n")

info('Execute: consumer.cmd("python consumer.py")\n')
info(producer.cmd("python producer.py") + "\n")

CLI(net)

net.stop()