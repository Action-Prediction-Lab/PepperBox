FROM ubuntu:20.04

# Avoid interactive prompts
ARG DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-tk \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Fix Locale for PyBullet GUI (often required)
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Install Python packages
# qibullet pulls in pybullet, numpy, cv2, etc.
# flask for the shim server
RUN pip3 install --no-cache-dir \
    qibullet \
    flask \
    numpy \
    pyzmq

# --- Legacy Support for Physical Robot (Python 2.7) ---
RUN apt-get update && apt-get install -y python2 libpython2.7 curl && \
    curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py && \
    python2 get-pip.py && \
    python2 -m pip install flask requests "pyzmq<20" && \
    rm -rf /var/lib/apt/lists/*

# pynaoqi SDK is supplied at runtime by bind-mounting the user's licit copy at
# /opt/pynaoqi-python2.7-2.5.7.1-linux64 (see setup.sh and the compose files).
ENV PYTHONPATH="${PYTHONPATH}:/opt/pynaoqi-python2.7-2.5.7.1-linux64/lib/python2.7/site-packages"

# Create non-root user
RUN useradd --create-home --shell /bin/bash pepperdev
USER pepperdev
WORKDIR /home/pepperdev

# Pre-create cache dir so downstream mounts inherit pepperdev ownership.
RUN mkdir .qibullet

# Copy Bridge Code
COPY --chown=pepperdev:pepperdev py3-naoqi-bridge /home/pepperdev/py3-naoqi-bridge

# Copy Simulation Code
COPY --chown=pepperdev:pepperdev src /home/pepperdev/src

# Copy Entrypoint
COPY --chown=pepperdev:pepperdev entrypoint.sh /home/pepperdev/entrypoint.sh

# Set PYTHONPATH so python can find the modules in src/ if needed, 
# though we will run them directly.
ENV PYTHONPATH="${PYTHONPATH}:/home/pepperdev/src"

# Expose Shim Port
EXPOSE 5000

# Default command: Manual shell
CMD ["/bin/bash"]
