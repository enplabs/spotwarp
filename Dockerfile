# Standard AI/ML developer runtime image
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install gpu-action client and Jupyter environment from PyPI
RUN pip install --no-cache-dir gpu-action jupyter notebook

# Create configuration directory
RUN mkdir -p /root/.config/gpu-action

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose default Jupyter Notebook port (optional for templates)
EXPOSE 8888

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
