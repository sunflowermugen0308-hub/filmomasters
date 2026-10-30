import { defineConfig } from "vite";

const API = "https://api.themoviedb.org/3";
const GENRES = new Map([
  [12, "Aventure"], [14, "Fantastique"], [16, "Animation"], [18, "Drame"],
  [27, "Horreur"], [28, "Action"], [35, "Comédie"], [36, "Histoire"],
  [37, "Western"], [53, "Thriller"], [80, "Crime"], [99, "Documentaire"],
  [878, "Science-fiction"], [9648, "Mystère"], [10402, "Musique"],
  [10749, "Romance"], [10751, "Familial"], [10752, "Guerre"],
  [10770, "Téléfilm"],
]);

function tmdbDiscovery() {
  async function handle(request, response, next) {
    const url = new URL(request.url || "/", "http://localhost");
    if (url.pathname !== "/api/tmdb/discover") {
      next();
      return;
    }

    const send = (status, data) => {
      response.writeHead(status, {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      });
      response.end(JSON.stringify(data));
    };

    if (request.method !== "GET") {
      send(405, { error: "Méthode non autorisée." });
      return;
    }

    const key = process.env.TMDB_API_KEY;
    if (!key) {
      send(503, { error: "TMDB_API_KEY n’est pas défini sur le serveur Vite." });
      return;
    }

    const year = Number(url.searchParams.get("year"));
    const page = Number(url.searchParams.get("page") || 1);
    const monthValue = url.searchParams.get("month");
    const month = monthValue === null ? null : Number(monthValue);
    const currentYear = new Date().getFullYear();
    if (!Number.isInteger(year) || year < 1870 || year > currentYear ||
        !Number.isInteger(page) || page < 1 || page > 500 ||
        (month !== null && (!Number.isInteger(month) || month < 1 || month > 12))) {
      send(400, { error: "Année, mois ou page invalide." });
      return;
    }

    const params = new URLSearchParams({
      language: "fr-FR",
      include_adult: "true",
      include_video: "false",
      page: String(page),
      sort_by: "vote_count.asc",
      "vote_count.gte": "0",
    });
    if (month === null) {
      params.set("primary_release_year", String(year));
    } else {
      const start = `${year}-${String(month).padStart(2, "0")}-01`;
      const end = new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
      params.set("primary_release_date.gte", start);
      params.set("primary_release_date.lte", end);
    }

    const headers = { accept: "application/json" };
    if (key.split(".").length === 3) {
      headers.Authorization = `Bearer ${key}`;
    } else {
      params.set("api_key", key);
    }

    try {
      const result = await fetch(`${API}/discover/movie?${params}`, {
        headers,
        signal: AbortSignal.timeout(20000),
      });
      if (!result.ok) {
        const status = result.status === 401 || result.status === 403 ? 502 : result.status;
        send(status, {
          error: result.status === 401 || result.status === 403
            ? "TMDB a refusé la clé API du serveur."
            : `TMDB a répondu avec le statut HTTP ${result.status}.`,
        });
        return;
      }

      const data = await result.json();
      send(200, {
        page: data.page,
        totalPages: Math.min(Number(data.total_pages) || 1, 500),
        results: (data.results || []).map((film) => ({
          id: film.id,
          t: film.title || film.original_title,
          o: film.original_title || "",
          d: "Film à découvrir",
          y: Number((film.release_date || "").slice(0, 4)),
          k: Number(film.vote_count) || 0,
          g: (film.genre_ids || []).map((id) => GENRES.get(id)).filter(Boolean),
          p: film.poster_path || "",
          img: "",
          adult: film.adult === true,
          r: film.adult === true ? 6 : film.vote_count >= 10000 ? 5 : film.vote_count >= 5000 ? 4 :
            film.vote_count >= 2000 ? 3 : film.vote_count >= 500 ? 2 :
              film.vote_count >= 100 ? 1 : 0,
        })).filter((film) => Number.isSafeInteger(film.id) && film.t && film.y),
      });
    } catch (error) {
      console.error("TMDB discovery request failed:",
        error instanceof Error ? error.name : "UnknownError");
      send(502, { error: "Impossible de joindre TMDB. Réessaie dans un instant." });
    }
  }

  return {
    name: "filmomasters-tmdb-discovery",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [tmdbDiscovery()],
  server: {
    host: "127.0.0.1",
  },
  preview: {
    host: "127.0.0.1",
  },
  build: {
    rollupOptions: {
      input: "FilmoMasters.html",
    },
  },
});
