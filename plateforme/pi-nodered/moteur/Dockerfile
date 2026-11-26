# Moteur d'alerte de l'équipe (plateforme/config/moteur_alerte.py) dans un conteneur.
# paho-mqtt < 2 : le script crée mqtt.Client() sans CallbackAPIVersion (API 1.x).
FROM python:3.12-slim
RUN pip install --no-cache-dir "paho-mqtt<2"
WORKDIR /work
ENV PYTHONUNBUFFERED=1
# pce92.db est la base SQLite écrite par Node-RED (flow S3), partagée par le volume /data.
CMD ["sh", "-c", "ln -sf /data/pce92.db pce92.db && exec python moteur_alerte.py"]
