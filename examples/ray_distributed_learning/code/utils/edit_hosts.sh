HOST=$(hostname)
sleep 0.5
IP=$(ip -f inet addr show $HOST-eth0 | awk '/inet / {print $2}' | cut -d'/' -f1)
ex -sc "%s/.*$HOST/$IP\t$HOST/g" -cx /etc/hosts
ifconfig eth0 down

