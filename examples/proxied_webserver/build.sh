#!/bin/sh

docker build -f Dockerfile.client -t demo_client .
docker build -f Dockerfile.nginx -t demo_nginx .
docker build -f Dockerfile.redis -t demo_redis .
docker build -f Dockerfile.server -t demo_server .