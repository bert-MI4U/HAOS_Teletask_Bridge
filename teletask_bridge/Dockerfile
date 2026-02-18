ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app
COPY app/ /app/

RUN if [ -f /app/requirements.txt ]; then \
      pip3 install --no-cache-dir -r /app/requirements.txt; \
    fi

COPY rootfs/ /
