# PepperBox

Build command:
```
docker build -t pepper-direct-env .
```

Run command: 
```
> docker run -it --rm \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $HOME/.Xauthority:/home/pepperdev/.Xauthority \
    -e XAUTHORITY=/home/pepperdev/.Xauthority \
    --name pepper-container \
    pepper-direct-env

```
