# SpotWarp v3.5.1 Production Docker Environment for SaladCloud Container Engine (SCE)
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Install system dependencies (including rsync & ssh client for delta-sync)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    rsync \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install spotwarp CLI and Jupyter environment
RUN pip install --no-cache-dir spotwarp jupyter notebook

# Prepare standard workspace & checkpoint directories
RUN mkdir -p /workspace/checkpoints /root/.spotwarp

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose default Jupyter / Readiness Probe port
EXPOSE 8888

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
