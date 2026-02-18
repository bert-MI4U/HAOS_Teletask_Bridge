ARG BUILD_FROM=ghcr.io/home-assistant/{arch}-addon-base-python3:latest
FROM $BUILD_FROM

# Copy application
WORKDIR /app
COPY app/ /app/

# Install dependencies
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy and allow run
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
