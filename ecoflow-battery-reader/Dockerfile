ARG BUILD_FROM=python:3.13-slim
FROM $BUILD_FROM

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ecoflow_battery.py delta3_descriptor.bin THIRD_PARTY.md LICENSE.hassio-ecoflow-cloud run.sh ./
RUN chmod +x /app/run.sh

CMD [ "/app/run.sh" ]
