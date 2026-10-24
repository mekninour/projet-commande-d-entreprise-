# Contrat d'interface — trame capteur (sous-projets A et B)

Transcription du document « contrat_interface_trame_capteur.pdf » fourni par OPALimpact aux deux équipes. **Le PDF original fait foi.** Les points ambigus sont listés à part, en fin de document, sans modifier la spécification.

## Principe

Le nœud capteur (sous-projet A, Brest) **encode** la trame. La chaîne de collecte (sous-projet B, Rennes) la **décode** et développe un **émulateur de nœud** qui génère des trames conformes. Toute extension passe par le champ réservé.

## Format de la charge utile LoRaWAN (12 octets, big-endian)

| Champ | Octets | Taille | Type | Description |
|---|---|---|---|---|
| `node_id` | 0–1 | 2 o | uint16 | Identifiant unique du nœud (1–65535), jamais réattribué |
| `water_mm` | 2–3 | 2 o | uint16 | Niveau d'eau en millimètres (0–65535) |
| `batt_cv` | 4 | 1 o | uint8 | Tension batterie (voir point ouvert n°1) |
| `seq` | 5–6 | 2 o | uint16 | Compteur de trame incrémental (détection de pertes) |
| `status` | 7 | 1 o | uint8 | Champ de bits : alerte seuil, défaut capteur, mode éco |
| `reserved` | 8–11 | 4 o | — | Extensions (à documenter) |

```
octet :   0    1  |  2    3  |   4    |  5    6  |   7    |  8  9 10 11
champ :  node_id  | water_mm | batt_cv|   seq    | status | reserved
```

## Exemple officiel

Nœud 3, niveau 1 240 mm, batterie 3,16 V, trame n°157, sans alerte :

```
00 03 04 D8 9E 00 9D 00 00 00 00 00
```

Il est repris dans [`trame/exemples/exemples_trames.csv`](../trame/exemples/exemples_trames.csv).

## Règles d'extension

- Les octets 0 à 7 sont obligatoires et non modifiables.
- Les octets 8 à 11 sont libres, **à condition de documenter tout ajout** (idéalement convenu avec Brest).
- Le **premier bit de `status`** est réservé à l'alerte de franchissement de seuil.
- Fréquence de référence : **1 trame / 30 min**. L'optimisation (émission sur événement) revient à l'équipe B et **ne change pas le format**.
- Le même format sert à la collecte de secours par port série USB.

## Jeux de données de test (équipe B)

Scénarios à fournir à l'émulateur : régime nominal, montée de crue rapide, crue extrême dépassant les seuils, pannes réseau. Des courbes réelles (Vigicrues) peuvent être rejouées.

## Points ouverts (non résolus par le contrat)

| N° | Point | Hypothèse de travail de l'équipe B | À trancher par |
|---|---|---|---|
| 1 | `batt_cv` en « centivolts » : 158 donnerait 1,58 V et non 3,16 V, et un uint8 plafonne à 2,55 V | 20 mV par unité (158 × 0,02 = 3,16 V ; 4,2 V = 210) | Brest et le client |
| 2 | « Premier bit » de `status` : MSB (0x80) ou LSB (0x01) ? Position des autres bits non définie | En attente | Brest (tâche P4) |
| 3 | Datation d'une mesure si la cadence varie (`seq` ne suffit pas) | Horodatage de la passerelle | Équipe B, à documenter |
