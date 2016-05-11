FROM ubuntu:14.04

RUN apt-get update \
    && apt-get install -y software-properties-common apt-transport-https ca-certificates wget \
    && apt-add-repository ppa:ansible/ansible \
    && apt-get update \
    && apt-get install -y ansible git \
    && wget --no-verbose https://get.docker.com/builds/Linux/x86_64/docker-1.9.1 -O /usr/bin/docker \
    && chmod +x /usr/bin/docker \
    && echo 'Done'

WORKDIR /containernet

COPY . /containernet/

RUN sed -i 's@git://@https://@g' util/install.sh \
    && echo 'localhost ansible_connection=local' >> /etc/ansible/hosts \
    && cd /containernet/ansible \
    && ansible-playbook docker.install.yml \
    && cd /containernet \
    && cp util/install.sh /tmp/install.sh \
    && cat /tmp/install.sh | awk 'NR==1{print; print "set -x"} NR!=1' > util/install.sh \
    && mkdir -p util/_deps \
    && util/install.sh -s util/_deps -fnv \
    && make develop \
    && echo 'Done'

ENTRYPOINT ["util/docker/entrypoint.sh"]
