# Use Ubuntu 22.04 LTS as a stable base
FROM ubuntu:22.04

# Avoid interactive prompts during installation
ARG DEBIAN_FRONTEND=noninteractive

# Install all system dependencies, PLUS a lightweight window manager and VNC
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python3-openssl \
    git \
    libx11-6 \
    libxext6 \
    libxtst6 \
    libxi6 \
    xkb-data \
    libglu1-mesa \
    avahi-daemon \
    sudo \
    tree \
    # --- VNC and Desktop Dependencies ---
    tigervnc-standalone-server \
    novnc \
    websockify \
    openbox \
    && apt-get clean

# Copy the required installer files into the image
COPY choregraphe-suite-2.5.10.7-linux64-setup.run /tmp/
COPY pynaoqi-python2.7-2.5.7.1-linux64.tar.gz /tmp/
# Install Choregraphe
RUN rm -rf "/opt/Softbank Robotics" && \
    chmod +x /tmp/choregraphe-suite-2.5.10.7-linux64-setup.run && \
    printf '1\ny\n' | /tmp/choregraphe-suite-2.5.10.7-linux64-setup.run

# Fix the libz.so.1 library conflict
RUN mv "/opt/Softbank Robotics/Choregraphe Suite 2.5/lib/libz.so.1" "/opt/Softbank Robotics/Choregraphe Suite 2.5/lib/libz.so.1.old" && \
    ln -s /lib/x86_64-linux-gnu/libz.so.1 "/opt/Softbank Robotics/Choregraphe Suite 2.5/lib/libz.so.1"
    
# Create a non-root user to work in
RUN useradd --create-home --shell /bin/bash pepperdev && usermod -aG sudo pepperdev && echo 'pepperdev ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Create a symlink to the Choregraphe installation directory
RUN ln -s "/opt/Softbank Robotics/Choregraphe Suite 2.5" /opt/choregraphe

# Create the Choregraphe config file with the license key
RUN mkdir -p /home/pepperdev/.config/"Aldebaran Robotics" && \
    cat <<EOF > /home/pepperdev/.config/"Aldebaran Robotics"/Choregraphe.conf
[General]
LicenseKey=425d5117485d46585b4f44525a0d43575a4051595a03465144445b5950585559580b4c5b125f44455014515e5e5b09564055515d58
LicenseValidation=465857475459425c5f514c50
RecorderToolbar%3A%3Avisible=true
ogreInitSucceeded=true
showGettingStartedAtStartup=true

[LogWidget]
InfiniteLogging=false

[MemoryKeyGrapheWidget]
SamplingPeriodSec=1

[Preferences]
AutomaticProjectContentUpdateConflictResolutionAction=0
AutomaticProjectContentUpdateConflictResolutionEnabled=false
userBoxLibraries2=@Invalid()
EOF

# Change ownership of the user's home directory and the choregraphe link
RUN chown -R pepperdev:pepperdev /home/pepperdev && chown -R pepperdev:pepperdev /opt/choregraphe

# Switch to the non-root user
USER pepperdev
WORKDIR /home/pepperdev

# Install pyenv for the new user
RUN curl https://pyenv.run | bash

# Add pyenv to the PATH environment variable
ENV PYENV_ROOT=/home/pepperdev/.pyenv
ENV PATH=$PYENV_ROOT/bin:$PATH

# Add pyenv init to the shell's config file
RUN echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Install Python 2.7.18 and set it as the default
RUN eval "$(pyenv init -)" && \
    pyenv install 2.7.18 && \
    pyenv global 2.7.18 && \
    pip install flask

# Copy the bridge code
# COPY py3-naoqi-bridge /home/pepperdev/py3-naoqi-bridge

# Install the pynaoqi SDK
RUN tar -xvf /tmp/pynaoqi-python2.7-2.5.7.1-linux64.tar.gz -C /home/pepperdev/

# Set environment variable for the SDK
ENV PYTHONPATH=/home/pepperdev/pynaoqi-python2.7-2.5.7.1-linux64/lib/python2.7/site-packages

RUN echo '#!/bin/bash' > /home/pepperdev/entrypoint.sh && \
    echo 'sudo /usr/sbin/avahi-daemon --daemonize' >> /home/pepperdev/entrypoint.sh && \
    echo '/opt/choregraphe/choregraphe' >> /home/pepperdev/entrypoint.sh && \
    chmod +x /home/pepperdev/entrypoint.sh

# Expose the port for the shim server
EXPOSE 5000

# Set the default command to our new startup script
CMD ["/home/pepperdev/entrypoint.sh"]



