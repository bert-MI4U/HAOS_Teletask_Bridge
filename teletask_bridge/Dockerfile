ARG BUILD_FROM=hassioaddons/base-python:latest
FROM $BUILD_FROM

# Install Python + pip (Alpine)
RUN apk add --no-cache python3 py3-pip

# App files
WORKDIR /app
COPY app/ /app/

# s6 services and any other rootfs files
COPY rootfs/ /
# Do NOT set CMD here; the base image's default CMD ["/init"] must remain

# Make s6 service scripts executable
RUN chmod +x /etc/services.d/teletask/run \
    && chmod +x /etc/services.d/teletask/finish
