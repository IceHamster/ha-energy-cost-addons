FROM ghcr.io/home-assistant/base:3.24-2026.10.3

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

COPY requirements.txt /requirements.txt

RUN apk add --no-cache --upgrade python3 tzdata \
    && apk add --no-cache --virtual .build-deps py3-pip \
    && python3 -m venv --without-pip /opt/venv \
    && python3 -m pip --python /opt/venv install --no-cache-dir --only-binary=:all: -r /requirements.txt \
    && apk del .build-deps

COPY run.sh /
COPY app.py /app.py

RUN chmod a+x /run.sh

CMD ["/run.sh"]
