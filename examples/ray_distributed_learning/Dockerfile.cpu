ARG OS_VERSION="22.04"
FROM ubuntu:${OS_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.11
ARG RAY_VERSION=2.8.0

# Update, add repositories, and install dependencies
RUN apt update && \
    apt install -y --no-install-recommends \
        wget \
        ca-certificates \
        python${PYTHON_VERSION} && \
    ln -s /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Install pip
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python get-pip.py && \
    rm get-pip.py

# Install required Python packages
RUN pip install torch torchvision ray==${RAY_VERSION} tqdm

# Install additional tools for containernet
RUN apt install -y --no-install-recommends \
        vim \
		net-tools \
		iputils-ping \
        iproute2

COPY code ./code
WORKDIR /code
