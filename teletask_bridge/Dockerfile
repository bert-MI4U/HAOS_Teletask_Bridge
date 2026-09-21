ARG BUILD_FROM=hassioaddons/base-python:latest
FROM $BUILD_FROM

WORKDIR /app
COPY app/requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt
COPY app/ /app/

# s6 services and any other rootfs files
COPY rootfs/ /

# Ensure scripts are executable and fix Windows line endings if needed
RUN chmod +x /etc/cont-init.d/* || true \
    && chmod +x /etc/services.d/teletask/run \
    && chmod +x /etc/services.d/teletask/finish \
    && sed -i 's/\r$//' /etc/cont-init.d/* /etc/services.d/teletask/run /etc/services.d/teletask/finish || true

# Do NOT set CMD here; the base image's default CMD ["/init"] must remain
