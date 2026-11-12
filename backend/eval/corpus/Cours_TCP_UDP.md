# Cours de réseaux — La couche transport : TCP et UDP

## 1. Rôle de la couche transport

La couche transport assure la communication de bout en bout entre deux applications. Elle s'appuie sur la couche réseau (IP), qui achemine les paquets sans garantie : un paquet IP peut être perdu, dupliqué ou arriver dans le désordre. Les applications sont identifiées par des numéros de port codés sur 16 bits, soit des valeurs de 0 à 65 535. Les ports de 0 à 1023 sont dits « bien connus » : le port 80 est associé à HTTP, le port 443 à HTTPS et le port 53 au DNS.

## 2. Le protocole TCP

TCP (Transmission Control Protocol) est un protocole orienté connexion, défini à l'origine dans la RFC 793 publiée en 1981. Avant tout échange de données, une connexion est établie par une poignée de main en trois temps : le client envoie un segment SYN, le serveur répond par un segment SYN-ACK, puis le client confirme avec un segment ACK.

### 2.1 Fiabilité

TCP garantit la fiabilité grâce à trois mécanismes complémentaires. Premièrement, chaque octet transmis est numéroté par un numéro de séquence, ce qui permet au destinataire de remettre les données dans l'ordre et de détecter les doublons. Deuxièmement, le destinataire renvoie des acquittements (ACK) cumulatifs indiquant le prochain octet attendu. Troisièmement, l'émetteur arme un temporisateur de retransmission : si l'acquittement n'arrive pas avant son expiration, le segment est retransmis. Une somme de contrôle (checksum) de 16 bits permet en outre de détecter les segments corrompus.

### 2.2 Contrôle de flux

Le contrôle de flux évite de saturer le récepteur. Celui-ci annonce dans chaque segment une fenêtre de réception, c'est-à-dire le nombre d'octets qu'il peut encore stocker dans son tampon. L'émetteur ne doit jamais envoyer plus de données non acquittées que la taille de cette fenêtre.

### 2.3 Contrôle de congestion

Le contrôle de congestion protège le réseau lui-même. L'émetteur maintient une fenêtre de congestion (cwnd). Pendant la phase de démarrage lent (slow start), cette fenêtre double à chaque aller-retour jusqu'à atteindre un seuil appelé ssthresh. Au-delà, la phase d'évitement de congestion augmente la fenêtre d'un seul segment par aller-retour. Lorsque trois acquittements dupliqués sont reçus, TCP déclenche une retransmission rapide (fast retransmit) sans attendre l'expiration du temporisateur.

### 2.4 Fermeture

La fermeture d'une connexion TCP s'effectue en quatre temps : chaque extrémité envoie un segment FIN qui doit être acquitté par l'autre.

## 3. Le protocole UDP

UDP (User Datagram Protocol) est un protocole sans connexion décrit dans la RFC 768. Il n'offre aucune garantie de livraison, d'ordre ou d'absence de duplication : il n'y a ni acquittement, ni retransmission, ni contrôle de congestion. Son en-tête ne fait que 8 octets, contre 20 octets au minimum pour l'en-tête TCP. Cette légèreté le rend adapté aux applications temps réel comme la voix sur IP, la diffusion vidéo en direct ou les jeux en ligne, ainsi qu'aux requêtes DNS, où la rapidité prime sur la fiabilité.

## 4. Comparaison synthétique

TCP convient aux applications qui exigent l'intégrité des données : le Web, la messagerie électronique ou le transfert de fichiers. UDP convient lorsque la latence est plus critique que la perte occasionnelle d'un datagramme. Le protocole QUIC, utilisé par HTTP/3, est construit au-dessus d'UDP et réimplémente la fiabilité et le contrôle de congestion dans l'espace utilisateur.
