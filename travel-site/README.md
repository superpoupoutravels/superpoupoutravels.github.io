# Wayfarer Log — carnet de voyage à partir de Polarsteps

Site statique (HTML/CSS/JS pur, aucun serveur ni build nécessaire) qui
transforme tes exports Polarsteps en un carnet de voyage en ligne, gratuit,
hébergé sur GitHub Pages.

## Mise en place (une seule fois)

1. Crée un compte GitHub si tu n'en as pas (gratuit) : https://github.com/join
2. Crée un nouveau dépôt (repo), par exemple nommé `wayfarer-log`
   - Bouton vert "New" sur https://github.com/new
   - Visibilité : Public (nécessaire pour GitHub Pages gratuit)
   - Ne coche aucune case d'initialisation (pas de README auto)
3. Sur ton ordinateur, dans le dossier de ce projet (`travel-site/`), lance :
   ```
   git init
   git add .
   git commit -m "Site initial"
   git branch -M main
   git remote add origin https://github.com/<ton-identifiant>/wayfarer-log.git
   git push -u origin main
   ```
4. Sur GitHub, va dans **Settings > Pages** du dépôt :
   - Source : "Deploy from a branch"
   - Branch : `main`, dossier `/ (root)`
   - Enregistre
5. Après une ou deux minutes, ton site est en ligne à l'adresse :
   `https://<ton-identifiant>.github.io/wayfarer-log/`
6. **Important** : ouvre `site_config.json` et renseigne `base_url` avec
   cette même adresse, par exemple :
   ```json
   { "base_url": "https://<ton-identifiant>.github.io/wayfarer-log" }
   ```
   Sans ça, les liens que tu partages sur WhatsApp/Facebook/X n'afficheront
   pas d'aperçu correct (image, titre, description) — voir la section
   "Partage des liens" plus bas.

Aucune commande de build : GitHub Pages sert directement les fichiers HTML.

## Ajouter un nouveau voyage

1. Exporte le voyage depuis Polarsteps : tu obtiens un dossier
   `nom-du-voyage_12345678/` contenant `trip.json`, `locations.json` et un
   sous-dossier par étape.
2. Place ce dossier n'importe où sur ton disque, puis lance :
   ```
   python3 scripts/convert_polarsteps.py /chemin/vers/nom-du-voyage_12345678
   ```
   (nécessite Python 3 et la bibliothèque Pillow : `pip install Pillow`.
   ffmpeg est recommandé mais optionnel — voir plus bas.)
3. Le script :
   - lit `trip.json`
   - calcule la date de chaque étape dans son **fuseau horaire local**
     (et non en UTC), pour éviter les décalages d'un jour
   - récupère la **photo de couverture que tu as choisie sur Polarsteps**
     (avec repli automatique sur la première photo disponible si le
     téléchargement échoue — export privé, lien expiré, etc.)
   - redimensionne et compresse chaque photo en **WebP**, en deux tailles :
     une vignette légère (grille, cartes) et une grande version (zoom) —
     nettement plus léger qu'un JPEG à qualité équivalente
   - **compresse les vidéos** avec ffmpeg si disponible (voir plus bas)
   - range tout ça dans `photos/<slug-du-voyage>/`
   - génère `data/trips/<slug-du-voyage>.json`
   - met à jour l'index `data/trips.json`
   - génère une **page statique dédiée** `voyages/<slug-du-voyage>.html`
     avec les bonnes balises de partage pour ce voyage précis
   - met à jour l'aperçu de partage de la page d'accueil (dernier voyage)
4. Vérifie en local si tu veux (`python3 -m http.server` puis
   `http://localhost:8000`), puis publie :
   ```
   git add .
   git commit -m "Ajoute le voyage <nom>"
   git push
   ```
5. Le site se met à jour automatiquement en 1-2 minutes.

Le script est **idempotent** : le relancer sur un voyage déjà traité ne
recompresse pas les vidéos déjà présentes et régénère proprement le reste.

## Vidéos et ffmpeg (optionnel mais conseillé)

Si `ffmpeg` est installé sur ta machine, le script compresse automatiquement
chaque vidéo (constaté sur le voyage Maroc : une vidéo de 10,9 Mo passe à
1,9 Mo, une autre de 3,4 Mo à 0,3 Mo — sans perte visible à l'écran).

Sans ffmpeg, les vidéos sont copiées telles quelles (le script te previent
dans son affichage). Pour l'installer :
- macOS : `brew install ffmpeg`
- Windows : https://ffmpeg.org/download.html (ou `winget install ffmpeg`)
- Linux : `sudo apt install ffmpeg`

## Partage des liens (WhatsApp, Facebook, X…)

Chaque voyage a sa propre page (`voyages/<slug>.html`) avec un titre, une
description et une image de partage qui lui sont propres. C'est nécessaire
car WhatsApp, Facebook ou X **n'exécutent pas le JavaScript** de la page
qu'ils prévisualisent : ils ne lisent que le HTML brut envoyé par le
serveur. Un site à page unique qui remplirait ces informations en
JavaScript (comme le fait `trip.html` en secours) ne serait donc jamais vu
correctement par ces aperçus.

Pour que l'image et l'URL de partage soient justes, `site_config.json`
doit contenir l'adresse réelle du site (`base_url`, voir plus haut). Tu
peux vérifier le rendu d'un lien avec, par exemple,
https://www.opengraph.xyz/ une fois le site en ligne.

## Fond de carte

Le site utilise les tuiles **OpenStreetMap standard** (`tile.openstreetmap.org`),
gratuites, sans clé et sans inscription — l'apparence sombre vient d'un simple
filtre CSS (`.leaflet-tile-pane` dans `assets/css/style.css`), pas d'un
fournisseur de carte "nuit" à part.

CARTO (un autre fournisseur de fonds de carte) proposait un style équivalent,
mais impose depuis fin août 2026 une clé API gratuite (inscription requise,
limite de 5 millions de requêtes/mois) — d'où ce choix d'OpenStreetMap qui
reste sans aucune formalité pour un site personnel comme celui-ci.

## Notes

- **Poids d'un voyage** : à titre d'exemple, le voyage Maroc (34 étapes,
  245 photos, 2 vidéos) pèse environ 64 Mo une fois converti — GitHub
  recommande de rester sous 1 Go par dépôt (gratuit jusqu'à 5 Go, avec
  avertissement au-delà de 1 Go). À surveiller si tu accumules beaucoup de
  voyages très riches en vidéos.
- **`locations.json`** n'est pas utilisé pour l'instant : les coordonnées de
  chaque étape sont déjà présentes dans `trip.json`. Si un futur export en a
  besoin, il faudra adapter le script.
- **Design** : personnalisable dans `assets/css/style.css` (les couleurs
  sont regroupées en haut du fichier). Le nom du site est à changer dans
  `index.html` et `scripts/templates/trip_template.html` si tu veux un
  autre nom que "Wayfarer Log".
- **`trip.html`** (à la racine) reste une page de secours qui fonctionne
  avec `?slug=...` — pratique pour prévisualiser un voyage en local avant
  de committer, mais ce n'est pas elle qui sert de lien de partage (utilise
  toujours les liens `voyages/<slug>.html` générés par le script).
