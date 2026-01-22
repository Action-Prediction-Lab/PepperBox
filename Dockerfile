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
    numpy

# Create app directory
WORKDIR /home/pepperdev

# Copy Bridge Code
COPY py3-naoqi-bridge /home/pepperdev/py3-naoqi-bridge

# Copy Simulation Code
COPY src /home/pepperdev/src

# Set PYTHONPATH so python can find the modules in src/ if needed, 
# though we will run them directly.
ENV PYTHONPATH="${PYTHONPATH}:/home/pepperdev/src"

# Expose Shim Port
EXPOSE 5000

# Default command: Manual shell
CMD ["/bin/bash"]

# Expose Shim Port
EXPOSE 5000

# Default command: Manual shell
CMD ["/bin/bash"]
