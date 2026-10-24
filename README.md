# PCE 92 — Chaîne de données & résilience pour la surveillance des crues

Projet Commande Entreprise n°92, IMT Atlantique (campus de Rennes, FISE, 2026-2027), pour **OPALimpact**.

Ce dépôt contient le code du **sous-projet B** : la chaîne de données qui va du nœud capteur jusqu'au tableau de bord. Le nœud capteur réel est développé à Brest (sous-projet A). Les deux équipes sont reliées par un [contrat d'interface](docs/contrat_interface.md) : une trame de 12 octets.

## Architecture

```
 Émulateur ESP32 ──LoRaWAN 868 MHz──> Passerelle Raspberry Pi ──> ChirpStack ──MQTT──> Node-RED
 (emulateur/)                         + concentrateur RAK5146      (passerelle/)          (plateforme/)
                                                                                           ├─ stockage de l'historique
                                                                                           └─ tableaux de bord
```

Enjeu central : **mesurer le gain** d'une transmission optimisée (moins de trames, même information) pour préserver l'autonomie des capteurs.

## Organisation du dépôt

| Dossier | Contenu | Binôme |
|---|---|---|
| [`trame/`](trame/) | Encodeur et décodeur de la trame de 12 octets, exemples de trames partagés | B2 (encodeur), B1 (décodeur) |
| [`emulateur/`](emulateur/) | Code ESP32 : pile LoRaWAN, rejeu des séries, modes d'émission, compteurs, tampon côté nœud | B3 |
| [`passerelle/`](passerelle/) | Raspberry Pi, concentrateur RAK, ChirpStack, stockage local, tests de coupure | B1 |
| [`plateforme/`](plateforme/) | Flux Node-RED, stockage, injecteur de trames de test, tableaux de bord | B1 |
| [`donnees/`](donnees/) | Scénarios Vigicrues nettoyés et leur format | B3 |
| [`mesures/`](mesures/) | Protocole du banc, données brutes des campagnes, analyse | B2, B3, B1 |
| [`docs/`](docs/) | Contrat d'interface, fiches de formation, documentation d'installation | Tous |

Les documents de gestion de projet (comptes rendus, livrables, Gantt) restent sur le **Google Drive** de l'équipe. Ce dépôt ne contient que le code et la documentation technique.

## Équipe

| Binôme | Membres | Lead |
|---|---|---|
| B1 Passerelle & plateforme | Nour Mekni, Mohamed Amine Dahbi | Nour Mekni |
| B2 Contrat, alertes & analyse | Sasha Le Roux, Gaetan Boulard | Sasha Le Roux |
| B3 Émulateur & campagnes | Brahima Diarrassouba, Mathéo Vignaud | Brahima Diarrassouba |

Chef de projet : Mathéo Vignaud. Tuteurs : Renzo Navas, Alexander Pelov.

## Démarrer

```bash
git clone https://github.com/mekninour/projet-commande-d-entreprise-.git
cd projet-commande-d-entreprise-
```

Puis lire [CONTRIBUTING.md](CONTRIBUTING.md) avant le premier commit, et le README du dossier sur lequel vous travaillez.

## Licence

À définir avec OPALimpact (le client a une démarche open source ; le choix de licence n'est pas encore validé).
