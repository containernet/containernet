## Using Containernet inside a container

### Build the image

In the repository's root directory:

```
docker build -t containernet -f hub.Dockerfile .
```


### Start the container

```
docker run -ti --rm=true --net=host --pid=host --privileged=true -v '/var/run/docker.sock:/var/run/docker.sock' containernet
```