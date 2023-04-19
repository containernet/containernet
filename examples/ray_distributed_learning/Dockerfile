# Use an official NVIDIA CUDA base image
ARG OS_VERSION="22.04"
ARG CUDA_VERSION="12.1.0"
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu${OS_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.8
ARG OPENMPI_VERSION=4.1.2
ARG RAY_VERSION=2.3.1

# Update, add repositories, and install dependencies
RUN apt-get update && \
    apt install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        git \
        ca-certificates \
        ssh \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-dev \
        python${PYTHON_VERSION}-distutils && \
    ln -s /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Install pip
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python get-pip.py && \
    rm get-pip.py

# Create symbolic links for CUDA include and lib directories
RUN ln -s /usr/local/cuda/include /usr/local/include/cuda && \
    ln -s /usr/local/cuda/lib64 /usr/local/lib/cuda

# Install OpenMPI
RUN wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-${OPENMPI_VERSION}.tar.gz && \
    tar -xzf openmpi-${OPENMPI_VERSION}.tar.gz && \
    cd openmpi-${OPENMPI_VERSION} && \
    ./configure --with-cuda --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    cd .. && rm -rf openmpi-${OPENMPI_VERSION}.tar.gz openmpi-${OPENMPI_VERSION}

# Set environment variables for OpenMPI
ENV PATH="/usr/local/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"

# Install required Python packages
RUN pip install torch torchvision && \
    pip install --force-reinstall numpy==1.23.* && \
    pip install mpi4py && \
    pip install ray==${RAY_VERSION} && \
    pip install protobuf==3.20.* && \
    pip install --force-reinstall numpy==1.23.* && \
    pip install tqdm

# Install pygloo
RUN git clone https://github.com/ray-project/pygloo.git && \
    wget https://github.com/bazelbuild/bazelisk/releases/download/v1.16.0/bazelisk-linux-amd64 && chmod +x bazelisk-linux-amd64 && mv bazelisk-linux-amd64 /usr/local/bin/bazel && \
    cd pygloo && python setup.py build && pip install .

# Install additional tools for containernet
USER root
RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		vim \
		net-tools \
		iputils-ping \
        iproute2

COPY code ./code
WORKDIR /code
