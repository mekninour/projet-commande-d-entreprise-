# PCE 92 — Chaîne de données & résilience pour la surveillance des crues

Projet Commande Entreprise n°92, IMT Atlantique (campus de Rennes, FISE, 2026-2027), pour **OPALimpact**.

Ce dépôt contient le code du **sous-projet B** : la chaîne de données qui va du nœud capteur jusqu'au tableau de bord et aux alertes. Le nœud capteur réel est développé à Brest (sous-projet A). Les deux équipes sont reliées par un [contrat d'interface](docs/contrat_interface.md) : une trame de 12 octets.

## Architecture

```
 Émulateur ESP32 ──LoRaWAN 868 MHz──> Passerelle Raspberry Pi ──> ChirpStack ──MQTT──> Node-RED
 (emulateur/)                         + concentrateur RAK5146      (passerelle/)          (plateforme/, alertes/)
                                                                                           ├─ stockage de l'historique
                                                                                           ├─ moteur d'alerte
                                                                                           └─ tableaux de bord
```

Enjeu central : **mesurer le gain** d'une transmission optimisée (moins de trames, même information) pour préserver l'autonomie des capteurs.

## Organisation du dépôt

| Dossier | Contenu | Binôme | Tâches L2 |
|---|---|---|---|
| [`trame/`](trame/) | Encodeur et décodeur de la trame de 12 octets, exemples de trames partagés | B2 (encodeur), B1 (décodeur) | E1, S1 |
| [`emulateur/`](emulateur/) | Code ESP32 : pile LoRaWAN, rejeu des séries, modes d'émission, compteurs, tampon côté nœud | B3 (+ Gaetan pour R3) | E2, E4, E5, E6, R3, R4 |
| [`passerelle/`](passerelle/) | Raspberry Pi, concentrateur RAK, ChirpStack, stockage local, tests de coupure | B1 | A2 à A5, R1, R2, R5 |
| [`plateforme/`](plateforme/) | Flux Node-RED, stockage, injecteur de trames de test, tableaux de bord | B1 | S2, S3, S5, AL5, AL6 |
| [`alertes/`](alertes/) | Seuils par site, moteur et objet d'alerte, tests d'alerte, export OPAL | B2 | AL1 à AL4, AL7, R6, G2 |
| [`donnees/`](donnees/) | Scénarios Vigicrues nettoyés et leur format | B3 | E3 |
| [`mesures/`](mesures/) | Protocole du banc, données brutes des campagnes, analyse | B2, B3, B1 | M1 à M5 |
| [`docs/`](docs/) | Contrat d'interface, fiches de formation, documentation d'installation | Tous | P2, D1 |
| [`outils/`](outils/) | Scripts du projet (création des issues de suivi) | Mathéo | P1 |

Les documents de gestion de projet (comptes rendus, livrables, Gantt) restent sur le **Google Drive** de l'équipe. Ce dépôt ne contient que le code et la documentation technique.

## Équipe

| Binôme | Membres | Lead |
|---|---|---|
| B1 Passerelle & plateforme | Nour Mekni, Mohamed Amine Dahbi | Nour Mekni |
| B2 Contrat, alertes & analyse | Sasha Le Roux, Gaetan Boulard | Sasha Le Roux |
| B3 Émulateur & campagnes | Brahima Diarrassouba, Mathéo Vignaud | Brahima Diarrassouba |

Chef de projet : Mathéo Vignaud. Tuteurs : Renzo Navas, Alexander Pelov.

## Suivi des tâches

Chaque tâche du L2 est une **issue** GitHub, nommée par son identifiant (`[E4] Rejeu des séries`), avec les labels de son lot et de son binôme. Voir l'onglet *Issues* et le [guide de contribution](CONTRIBUTING.md).

## Démarrer

```bash
git clone https://github.com/mekninour/projet-commande-d-entreprise-.git
cd projet-commande-d-entreprise-
```

Puis lire [CONTRIBUTING.md](CONTRIBUTING.md) avant le premier commit, et le README du dossier sur lequel vous travaillez.

## Licence

À définir avec OPALimpact (le client a une démarche open source ; le choix de licence n'est pas encore validé).
