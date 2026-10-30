# FilmoMasters

## Lancer le site

Définir la clé TMDB côté serveur, puis lancer Vite :

```sh
npm install
TMDB_API_KEY=votre_cle npm run dev
```

Ouvrir ensuite l’adresse affichée par Vite, suivie de `/FilmoMasters.html`.
La clé reste dans le processus Node et n’est jamais envoyée au navigateur.

Les films sont découverts progressivement : les boosters garantissent une nouvelle carte issue des pages TMDB, sans votes minimum. La progression est sauvegardée dans le navigateur. Les requêtes parcourent les années puis les mois si une année atteint la limite de pagination TMDB.
Les titres que TMDB signale comme réservés aux adultes sont aussi inclus.
Ces films reçoivent la rareté P, au-dessus de Légendaire ; le succès « Première P » se débloque en obtenant une carte de cette catégorie.
Le profil (avatar à initiales et présentation) et le réglage du son sont disponibles dans le menu. Les albums comprennent des filmographies, une sélection de lauréats de festivals et une sélection de titres du sondage Sight and Sound 2022. Les cartes fantômes indiquent les titres absents du catalogue chargé.
L’interface s’adapte aux écrans mobiles, tablettes et ordinateurs ; dans le Festival, toucher une carte ouvre sa fenêtre d’enchère.

Le Festival, les enchères et les profils d’amis sont locaux à ce navigateur : il n’y a pas de comptes partagés. Les enchères durent de 1 à 12 heures ; sans offre, une carte revient à son propriétaire à l’expiration. La boutique présente des offres informatives sans paiement.

L’interface utilise la police « Fifties Movies » si elle est installée localement. Installez-la depuis la page DaFont fournie, puis rechargez le site ; une police de secours est utilisée sinon.

## Charger les films TMDB

Définir `TMDB_API_KEY`, puis générer le catalogue :

```sh
export TMDB_API_KEY=votre_cle
python3 fetch_tmdb.py --pages 100 --posters 300
```

Le script écrit `public/films.json`, lu automatiquement par le site et inclus dans le build Vite. Sans ce fichier, le catalogue local reste disponible ; la découverte progressive nécessite une clé TMDB et le serveur Vite en local ou la fonction Netlify en production.

## Déployer sur Netlify

Le dépôt se construit avec `npm run build` et publie le dossier `dist`. La découverte progressive TMDB utilise une fonction Netlify ; configurez `TMDB_API_KEY` dans les variables d’environnement du site Netlify avant le déploiement. La clé ne doit pas être ajoutée au dépôt.
