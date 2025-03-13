# Use Python 3.11 slim image as the base
FROM python:3.11-slim

# Set default environment variables
ENV RUNTIME_API_HOST=http://localhost
ENV CHROME_INSTANCE_PATH=/usr/bin/chromium
ENV HOME=/home/ubuntu

# Install system dependencies: Chromium, bash, sudo, Node.js, npm, pip3, and bc
# https://gist.github.com/jlia0/db0a9695b3ca7609c9b1a08dcbf872c9#file-modules-L185
RUN apt-get update && \
    apt-get install -y chromium python3-venv bash sudo curl bc && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.18.0 and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    node -v && npm -v  # Verify installation

# Create a non-root user and add to sudoers
RUN useradd -m -s /bin/bash ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu

# Create manus user
RUN useradd -m -s /bin/bash manus

# Create the target directory structure and set proper permissions
RUN mkdir -p /opt/.manus/.sandbox-runtime && \
    chown -R ubuntu:ubuntu /opt/.manus

# Set proper permissions for Python directories (must be done as root)
RUN chmod -R 755 /usr/local/lib/python*

# Switch to non-root user
USER ubuntu

# Set working directory
WORKDIR /opt/.manus/.sandbox-runtime

# Copy the repository files into the container
COPY --chown=ubuntu:ubuntu . /opt/.manus/.sandbox-runtime/

# Create a Python virtual environment in the working directory
RUN python -m venv venv

# Upgrade pip and install Python dependencies inside the virtual environment
RUN ./venv/bin/pip install --upgrade pip && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt

# Create the secrets directory with proper permissions
RUN mkdir -p $HOME/.secrets && \
    chmod 700 $HOME/.secrets

# Expose the internal API port
EXPOSE 8330

# Use the virtual environment's Python to run the start_server.py script
CMD ["./venv/bin/python", "start_server.py"]