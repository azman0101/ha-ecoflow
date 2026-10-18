FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/azman0101/ha-ecoflow" \
      org.opencontainers.image.description="EcoFlow DELTA 3 Reader - Home Assistant add-on" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ecoflow_battery.py ecoflow_discovery.py prepare_config.py delta3_descriptor.bin THIRD_PARTY.md LICENSE.hassio-ecoflow-cloud run.sh ./
RUN chmod +x /app/run.sh

CMD [ "/app/run.sh" ]
