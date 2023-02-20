FROM rayproject/ray-ml:2.2.0-cpu
USER root
RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		vim \
		net-tools \
		iputils-ping \
        iproute2

RUN pip install protobuf==3.20.*


COPY code ./code