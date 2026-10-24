# Passerelle Raspberry Pi et ChirpStack

**Binôme :** B1 Passerelle & plateforme

Configuration de la passerelle : Raspberry Pi, concentrateur RAK5146 (EU868), packet forwarder, ChirpStack v4 et sa base, stockage local en cas de coupure d'internet.

Structure proposée :

```
passerelle/
├── raspberry/      # préparation du Pi (scripts, services systemd)
├── concentrateur/  # configuration du RAK5146 et du packet forwarder
├── chirpstack/     # docker-compose, configuration EU868, profils (sans clés)
└── resilience/     # stockage local, tests de coupure, redémarrage automatique
```

Précaution : **ne jamais alimenter le RAK sans son antenne**.
