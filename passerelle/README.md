# Passerelle Raspberry Pi et ChirpStack

Configuration de la passerelle : Raspberry Pi, concentrateur RAK5146 (EU868), packet forwarder, ChirpStack v4 et sa base, stockage local en cas de coupure d'internet.

Structure proposée :

```
passerelle/
├── raspberry/      # A2 : préparation du Pi (scripts, services systemd)
├── concentrateur/  # A3 : configuration du RAK5146 et du packet forwarder
├── chirpstack/     # A4, A5 : docker-compose, configuration EU868, profils (sans clés)
└── resilience/     # R1, R2, R5 : stockage local, tests de coupure, redémarrage automatique
```

Précaution : **ne jamais alimenter le RAK sans son antenne**.

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| A2 | Préparation du Raspberry Pi | OS, SSH, IP fixe ou nom d'hôte, mises à jour | Mohamed Amine Dahbi | A1 | Socle |
| A3 | Concentrateur LoRa | RAK5146 + Pi HAT + antenne, packet forwarder actif, paquets visibles | Mohamed Amine Dahbi | A2, livraison RAK | Après |
| A4 | Installation de ChirpStack | ChirpStack v4 + MQTT + base, interface web ; Docker sur PC puis Pi | Mohamed Amine Dahbi | A2 (ou Docker sur PC) | Stretch |
| A5 | Configuration ChirpStack | EU868, passerelle en ligne, application, profil classe A OTAA | Mohamed Amine Dahbi | A3, A4 | Après |
| R1 | Stockage local passerelle | Données conservées si internet coupé, rattrapage | Mohamed Amine Dahbi | S3 | Après |
| R2 | Test coupure internet | Coupure puis reprise sans perte, journal | Mohamed Amine Dahbi | R1 | Après |
| R5 | Coupure alimentation passerelle | Redémarrage auto de la chaîne | Mohamed Amine Dahbi | A5, S2 | Après |

État à jour : voir les issues GitHub correspondantes.
