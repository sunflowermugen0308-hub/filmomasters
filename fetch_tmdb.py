#!/usr/bin/env python3
"""FilmoMasters : récupère les films les plus votés de TMDB et écrit films.json.

Usage :
    export TMDB_API_KEY=votre_cle          (Windows : set TMDB_API_KEY=votre_cle)
    python3 fetch_tmdb.py --pages 100 --posters 300

Aucune dépendance à installer (bibliothèque standard uniquement).
"""
import argparse, base64, json, os, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"
HEADERS = {"User-Agent": "FilmoMasters"}


def get(url, params=None, raw=False, tries=5):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (401, 403):
                raise RuntimeError("Clé API refusée par TMDB (HTTP %d)." % e.code) from e
            if e.code != 429 and not 500 <= e.code < 600:
                raise RuntimeError("Erreur TMDB (HTTP %d)." % e.code) from e
            last_error = "HTTP %d" % e.code
            delay = 1 + attempt
            if e.code == 429:
                try:
                    delay = max(1, int(e.headers.get("Retry-After", 2)))
                except (TypeError, ValueError):
                    delay = 2
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = str(e)
            delay = 1 + attempt
        if attempt + 1 < tries:
            time.sleep(delay)
    raise RuntimeError("Échec de la requête TMDB après %d tentatives (%s)." %
                       (tries, last_error or "erreur inconnue"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=100, help="pages de 20 films (max 500)")
    ap.add_argument("--min-votes", type=int, default=300, help="votes TMDB minimum")
    ap.add_argument("--posters", type=int, default=300, help="nombre d'affiches à intégrer (les plus populaires)")
    ap.add_argument("--poster-size", default="w154", choices=["w92", "w154", "w185", "w342"])
    ap.add_argument("--out", default=os.path.join("public", "films.json"))
    a = ap.parse_args()
    if not 1 <= a.pages <= 500:
        ap.error("--pages doit être compris entre 1 et 500.")
    if a.min_votes < 0:
        ap.error("--min-votes doit être positif ou nul.")
    if a.posters < 0:
        ap.error("--posters doit être positif ou nul.")

    key = os.environ.get("TMDB_API_KEY") or input("Clé API TMDB : ").strip()
    if not key:
        ap.error("Définissez TMDB_API_KEY ou saisissez une clé API TMDB.")
    base = {"language": "fr-FR"}
    if key.count(".") == 2:  # jeton v4 (Bearer)
        HEADERS["Authorization"] = "Bearer " + key
    else:  # clé v3
        base["api_key"] = key

    # 1) liste des films les plus votés
    ids = []
    for p in range(1, min(a.pages, 500) + 1):
        d = get(API + "/discover/movie", {**base, "sort_by": "vote_count.desc",
                "include_adult": "true", "include_video": "false",
                "vote_count.gte": a.min_votes, "page": p})
        if not d or not d.get("results"):
            break
        ids += [m["id"] for m in d["results"]]
        print("\rListe : page %d" % p, end="", flush=True)
        if p >= d.get("total_pages", p):
            break
    ids = list(dict.fromkeys(ids))
    print("\n%d films trouvés, récupération des détails..." % len(ids))
    if not ids:
        raise RuntimeError("TMDB n'a renvoyé aucun film pour ces critères.")

    # 2) détails + réalisateur
    def detail(i):
        d = get(API + "/movie/%d" % i, {**base, "append_to_response": "credits"})
        if not d:
            return None
        dirs = [c["name"] for c in d.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
        y = (d.get("release_date") or "")[:4]
        if not dirs or not y.isdigit():
            return None
        return {"id": d["id"], "t": d.get("title") or d.get("original_title"),
                "o": d.get("original_title"), "d": " & ".join(dirs[:2]), "y": int(y),
                "k": d.get("vote_count", 0), "g": [g["name"] for g in d.get("genres", [])],
                "p": d.get("poster_path"), "adult": d.get("adult") is True}

    films = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, f in enumerate(ex.map(detail, ids), 1):
            if f:
                films.append(f)
            if n % 50 == 0:
                print("\rDétails : %d/%d" % (n, len(ids)), end="", flush=True)
    if not films:
        raise RuntimeError("Aucun film n'a pu être récupéré avec ses détails.")
    films.sort(key=lambda f: -f["k"])

    # 3) rareté par rang (proxy : votes TMDB)
    n = len(films)
    for rank, f in enumerate(films):
        q = rank / n
        f["r"] = 6 if f["adult"] else 5 if q < .01 else 4 if q < .04 else 3 if q < .12 else 2 if q < .30 else 1 if q < .60 else 0

    # 4) affiches intégrées (base64) pour les plus populaires
    top = [f for f in films if f["p"]][:a.posters]
    print("\nTéléchargement de %d affiches..." % len(top))

    def img(f):
        try:
            b = get("%s/%s%s" % (IMG, a.poster_size, f["p"]), raw=True)
        except RuntimeError:
            return False
        if b:
            f["img"] = "data:image/jpeg;base64," + base64.b64encode(b).decode()
            return True
        return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        poster_results = list(ex.map(img, top))
    failed_posters = poster_results.count(False)
    if failed_posters:
        print("%d affiche(s) indisponible(s) ou en échec; les films restent dans l'export." %
              failed_posters, file=sys.stderr)

    output_dir = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(output_dir, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_dir,
                                         prefix=".films-", suffix=".tmp", delete=False) as fh:
            temp_path = fh.name
            json.dump(films, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp_path, a.out)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    mo = os.path.getsize(a.out) / 1e6
    print("%s écrit : %d films, %.1f Mo." % (a.out, n, mo))
    if mo > 12:
        print("Attention : au-delà de ~12 Mo, réduisez --posters ou --poster-size.")


if __name__ == "__main__":
    main()
