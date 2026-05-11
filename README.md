# PepperBox

A containerised backend for developing applications with Aldebaran/SoftBank's Pepper robots.

A single image runs both modes; the `NAOQI_IP` environment variable selects whether you connect with a:

- **Physical robot** — `NAOQI_IP=<robot.ip>` runs the Python 2 `pynaoqi` bridge.
- **Simulation** — `NAOQI_IP=127.0.0.1` (or unset) runs the Python 3 `qiBullet` simulator.

In both cases a Flask **shim server** on port 5000 exposes a unified HTTP API to your Python 3 client code. The client is agnostic to whether you connect to a physical or simulated robot. 

## What's in the image

qiBullet, a Python 2.7 runtime, the bridge code (`py3-naoqi-bridge/`), and the simulation shim (`src/`). The pynaoqi SDK is supplied separately by the user at runtime via a bind-mount; see [Physical robot setup](#physical-robot-setup) below.

Simulation runs without anything else.

## Prerequisites

- Docker
- Linux host (uses `--net=host` and `/dev/dri`)
- For physical-robot use: a Pepper or NAO on a network reachable from the host

## Physical robot setup

You will need the SoftBank Robotics pynaoqi SDK once. PepperBox does not ship it; the `setup.sh` script fetches it directly from Aldebaran's still-live CDN, with a Wayback Machine fallback, and verifies the SHA256.

```bash
./setup.sh
```

This places the SDK at `~/.pepperbox/pynaoqi-python2.7-2.5.7.1-linux64/`. `run.sh` and the docker-compose stack then bind-mount that directory into the container at `/opt/pynaoqi-python2.7-2.5.7.1-linux64`.

If both download sources are unreachable, the script prints the expected filename, size, and SHA256 so you can supply the file from any byte-identical mirror:

```
filename: pynaoqi-python2.7-2.5.7.1-linux64.tar.gz
size:     51743305 bytes
sha256:   d2060ad69f87481f0dda82ede6c70c3b65afa6f1bf06e2c107c2e373d26d92c2
```

Once the SDK is in place, set the robot's address and run:

```bash
export NAOQI_IP=192.168.123.50   # your robot's IP
export NAOQI_PORT=9559
./run.sh
```

`entrypoint.sh` checks the SDK is mounted and the robot is reachable before starting the bridge, and reports a specific error if either is wrong.

## Simulation

```bash
./run.sh
```

With `NAOQI_IP` unset or `127.0.0.1`, qiBullet starts. On first run, qiBullet's installer needs to write SoftBank-licensed Pepper URDF and mesh assets to `~/.qibullet`. To acknowledge the licence (a one-time step), set:

```bash
export PEPPERBOX_ACCEPT_SOFTBANK_LICENSE=1
./run.sh
```

The relevant licence files ship with the qiBullet package; see the project at `softbankrobotics-research/qibullet`.

## Build

```bash
docker build -t pepper-box:latest .
```

The build does not include any SoftBank Robotics proprietary content. It can be run on any host without a Pepper or pynaoqi present.

## Connection details

The shim server on `:5000` is your unified entry point.

| Mode         | Backend                          | Switched by                    |
| ------------ | -------------------------------- | ------------------------------ |
| Simulation   | Python 3 + qiBullet              | `NAOQI_IP=127.0.0.1` or unset  |
| Physical     | Python 2 + pynaoqi bridge        | `NAOQI_IP=<remote IP>`         |

Client code (Python 3) is identical in either case.

## Layout

```
PepperBox/
├── Dockerfile
├── entrypoint.sh           # mode dispatch + pre-flight checks
├── run.sh                  # standalone host launcher
├── setup.sh                # one-shot pynaoqi installer
├── src/
│   ├── shim_server.py      # qiBullet (sim) shim
│   └── setup_wizard.py     # qiBullet asset installer
└── py3-naoqi-bridge/
    ├── shim_server.py      # pynaoqi (physical) shim
    ├── video_streamer.py
    └── ...                 # NAOqi-side services
```

## Licence

PepperBox itself is BSD 3-Clause; see `LICENSE`. The pynaoqi SDK and the Pepper URDF/mesh assets bundled with qiBullet are SoftBank Robotics property and remain under SoftBank's terms.
