ARG BUILD_FROM=hassioaddons/base-python:latest
FROM $BUILD_FROM

# Install Python + pip (Alpine)
RUN apk add --no-cache python3 py3-pip

# App files
WORKDIR /app
COPY app/ /app/

RUN if [ -f /app/requirements.txt ]; then \
      (command -v pip3 >/dev/null 2>&1 && pip3 --version) || true; \
      (command -v pip >/dev/null 2>&1 && pip --version) || true; \
      python3 -m ensurepip --upgrade || true; \
      python3 -m pip install --upgrade pip setuptools wheel; \
      python3 -m pip install --no-cache-dir -r /app/requirements.txt; \
    fi

# s6 services and any other rootfs files
COPY rootfs/ /
# Do NOT set CMD here; the base image's default CMD ["/init"] must remain
