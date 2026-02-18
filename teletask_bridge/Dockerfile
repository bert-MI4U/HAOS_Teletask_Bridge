ARG BUILD_FROM=hassioaddons/base-python:latest
FROM $BUILD_FROM

# Install Python + pip (Alpine)
RUN apk add --no-cache python3 py3-pip

# ---- Create a venv and preinstall deps there ----
# Put the venv in a stable location
RUN python3 -m venv /opt/venv
# Make venv tools available on PATH for subsequent layers (and runtime)
ENV PATH="/opt/venv/bin:${PATH}"

# App files
WORKDIR /app
COPY app/ /app/

# Install your requirements into the venv (build-time, no PEP668 issues)
# If you don't have requirements.txt, this will just skip the step.
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    if [ -f /app/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/requirements.txt; \
    else \
        pip install --no-cache-dir gmqtt; \
    fi

# s6 services and any other rootfs files
COPY rootfs/ /

# Ensure scripts are executable and fix Windows line endings if needed
RUN chmod +x /etc/cont-init.d/* || true \
    && chmod +x /etc/services.d/teletask/run \
    && chmod +x /etc/services.d/teletask/finish \
    && sed -i 's/\r$//' /etc/cont-init.d/* /etc/services.d/teletask/run /etc/services.d/teletask/finish || true

# Do NOT set CMD here; the base image's default CMD ["/init"] must remain
