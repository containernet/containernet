FROM ubuntu:trusty
MAINTAINER manuel@peuster.de

RUN apt-get update \
    && apt-get install -y software-properties-common apt-transport-https ca-certificates wget \
    && apt-add-repository ppa:ansible/ansible \
    && apt-get update \
    && apt-get install -y ansible git curl python-pip \
    && curl -fsSL https://get.docker.com/gpg | apt-key add - \
    && curl -fsSL https://get.docker.com/ | sh \
    && chmod +x /usr/bin/docker \
    && pip install -U setuptools \
    && pip install -U pytest \
    && pip install -U urllib3 \
    && pip install -U docker-py \
    && echo 'Done'

WORKDIR /containernet

COPY . /containernet/

RUN sed -i 's@git://@https://@g' util/install.sh \
    && echo 'localhost ansible_connection=local' >> /etc/ansible/hosts \
    && cd /containernet \
    && cp util/install.sh /tmp/install.sh \
    && cat /tmp/install.sh | awk 'NR==1{print; print "set -x"} NR!=1' > util/install.sh \
    && mkdir -p util/_deps \
    && util/install.sh -s util/_deps -fnv \
    && make develop \
    && echo 'Done'

ENTRYPOINT ["util/docker/entrypoint.sh"]
