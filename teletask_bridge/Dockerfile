ARG BUILD_FROM=hassioaddons/base-python:latest
FROM $BUILD_FROM

# Install Python + pip (Alpine)
RUN apk add --no-cache python3 py3-pip

# App files
WORKDIR /app
COPY app/ /app/

# Python dependencies (if your app has requirements.txt)
RUN if [ -f /app/requirements.txt ]; then \
      pip3 install --no-cache-dir -r /app/requirements.txt; \
    fi

# s6 services and any other rootfs files
COPY rootfs/ /
# Do NOT set CMD here; the base image's default CMD ["/init"] must remain
