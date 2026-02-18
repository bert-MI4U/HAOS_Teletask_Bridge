ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM
RUN apk add --no-cache python3 py3-pip
WORKDIR /app
COPY app/ /app/
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
