# Fantasyesbot

Discord-bot for **Eliteserien Fantasy** som holder ligaene oppdatert med rundeinfo, spillernyheter, skader og lagstatistikk.

---

## Hva gjør boten?

- **Automatiske deadlinepåminnelser** — Sender melding i nyhetskanalen 1 time før rundestarten med rollemention
- **Spillernyheter og priser** — Sjekker jevnlig for prisendringer og skadeoppdateringer fra bootstrap-API-et og varsler om endringer
- **Rundesummering** — Poster rundesammendrag med toppliste, chips brukt og rundens lag når runden er ferdig
- **Ligatopplisteepostsporing** — Rangering med Discord-brukernavn knyttet til FPL-lag
- **Lag-picks** — Vis hva enkeltspillere har på laget sitt denne runden inkl. live poeng
- **Flause-tabellen** — Ranger hvem som har gjort de dårligste byttes- og benkbeslutninger

---

## Kommandoer

| Kommando | Beskrivelse |
|---|---|
| `!deadline [runde]` | Rundeinfo for aktiv eller angitt runde. Eks: `!deadline` · `!deadline 5` |
| `!nyheter [antall]` | Aktive skader og nyheter akkurat nå. Eks: `!nyheter` · `!nyheter 50` |
| `!skade [lag\|antall]` | Skader per lag, eller siste N meldinger. Eks: `!skade Rosenborg` · `!skade 30` |
| `!rangering` | Fullstendig ligatabell med poeng og forrige ukes rangering |
| `!flause` | Ranger hvem som har gjort de dårligste bytter/benkbeslutninger denne runden |
| `!hevdlag <lagnavn>` | Knytt deg selv til ditt Fantasy-lag. Eks: `!hevdlag Bakromshelvette` |
| `!lagetmitt` | Vis ditt lags nåværende picks |
| `!lag [@mention\|brukernavn]` | Vis et lag. Uten argument: ditt eget. Eks: `!lag @madcow` · `!lag madcow` |
| `!påminnelse [log]` | Send deadlinepåminnelse til nyhetskanal nå. Legg til `log` for å teste i log-kanal |
| `!sync` | Henter fersk Fantasy-data og poster eventuelle endringer til nyhetskanal nå |
| `!stopp [alt]` | Stopper automatisk posting. Med `alt`: stopper også kommandolytting *(kun admin, log-kanal)* |
| `!start` | Aktiverer posting og kommandolytting igjen *(kun admin, log-kanal)* |
| `!lagkobling @bruker <lagnavn>` | Koble en bruker til et lag *(kun admin, log-kanal)* |
| `!update` | Git pull + omstart *(kun admin)* |
| `!hjelp` | Vis kommandooversikt *(kun fra log-kanal)* |

---

## Arkitektur

```
bot.py                  – Inngangspunkt, Discord-kommandoer og schedulerte tasks
main.py                 – FPL API-kall med caching (events, standings, picks, live)
bootstrap_diff.py       – Sammenligner bootstrap-snapshot for pris-/nyhetsendringer
team_claims.py          – Kobler Discord-brukere til FPL-lag (persistent via GCS)
posted_tracker.py       – Deduplicerer utsendte meldinger på tvers av restarter
gcs_utils.py            – Lese/skrive JSON til Google Cloud Storage
cache_utils.py          – Lokal filcache med TTL
news_log.py             – Logging av skade-/nyhetshistorikk
servers.json            – Per-server konfig: guild_id, kanaler, liga-ID, rolle-ID
```

### Schedulerte tasks

| Task | Intervall | Hva den gjør |
|---|---|---|
| `deadline_reminder` | 15 min | Sender påminnelse 1t før deadline med rollemention |
| `news_update` | 30 min* | Sjekker prisendringer og skader, varsler om endringer |
| `round_completed_check` | 15 min | Poster rundesammendrag når `top_element_info` er tilgjengelig |

*Konfigurerbar via `NEWS_INTERVAL_MINUTES`

---

## Deployment (Google Cloud Run)

Boten kjører som en langtidslevende container med persistent WebSocket til Discord.

```bash
gcloud run deploy fantasyesbot \
  --image gcr.io/YOUR_PROJECT/fantasyesbot \
  --min-instances=1 --max-instances=1 \
  --set-env-vars DISCORD_BOT_TOKEN=...,BASE_API_URL=...,GCS_BUCKET=...
```

**Slå av (offseason):**
```bash
gcloud run services update fantasyesbot --min-instances=0 --max-instances=0
```

**Slå på igjen:**
```bash
gcloud run services update fantasyesbot --min-instances=1 --max-instances=1
```

### Miljøvariabler

| Variabel | Påkrevd | Standard | Beskrivelse |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | ✅ | — | Discord bot-token |
| `BASE_API_URL` | ✅ | — | FPL API-base-URL |
| `GCS_BUCKET` | ✅ | — | GCS-bøttenavn for persistent state |
| `NEWS_INTERVAL_MINUTES` | — | 30 | Intervall for nyhetssjekk (min) |
| `BOOTSTRAP_CACHE_TTL_MINUTES` | — | 180 | Cache-TTL for bootstrap-static |
| `EVENTS_CACHE_TTL_MINUTES` | — | 320 | Cache-TTL for event-liste |
| `STANDINGS_CACHE_TTL_MINUTES` | — | 120 | Cache-TTL for ligatabell |
| `LIVE_CACHE_TTL_MINUTES` | — | 120 | Cache-TTL for live-poeng per runde |
| `PICKS_CACHE_TTL_MINUTES` | — | 10080 | Cache-TTL for lagoppstilling (7 dager) |
| `DREAM_TEAM_CACHE_TTL_MINUTES` | — | 10080 | Cache-TTL for rundens lag (7 dager) |
| `ADMIN_USERNAMES` | — | galku | Kommaseparert liste over admin-brukernavn |

---

## Releases / Endringslogg

### v2.4 — Per-server stopp/start og admin fra servers.json (mars 2026)
- `!stopp [alt]` — stopper automatisk posting, med `alt` også kommandolytting
- `!start` — aktiverer posting og kommandolytting igjen
- Admin-brukere konfigureres nå per server i `servers.json` (ikke lenger env-var)
- Boten poster per-server statusmelding til log-kanal ved oppstart etter restart
- Stoppet tilstand overlever restart via GCS-persistent `server_state.json`

### v2.3 — Polering og display name (mars 2026)
- Alle feilmeldinger og tomme-resultat-svar viser nå hvem som kjørte kommandoen (`– **brukernavn**`)
- Apostrofvarianter normalisert ved lagsøk — `Timothy's Kelnere` og `Timothy's Kelnere` matcher nå
- All caching konfigurerbar via `.env` med fornuftige standardverdier; API-kall kraftig redusert

### v2.2 — Lagkobling og flause-tabellen (mars 2026)
- `!flause` — ranger hvem som led mest av dårlige bytter og benkbeslutninger denne runden
- `!hevdlag` / `!lag` / `!lagetmitt` — koble Discord-bruker til FPL-lag og se picks med live poeng
- `!lagkobling` — admin-kommando for å koble andre brukere til lag
- `!rangering` viser Discord-brukernavn ved siden av lagnavn
- Duplikatbeskyttelse: boten nekter å overskrive eksisterende lagkobling uten admin
- Ligatabell henter nå alle sider (full paginering)

### v2.1 — Kommandoutvidelser (mars 2026)
- `!nyheter`, `!skade`, `!sync`, `!update`, `!påminnelse`, `!hjelp` lagt til
- Fiks GCS fallback-bug som gjorde at `posted_tracker` nullstilte seg ved omstart
- Nyheter routes til nyhetskanal, systemlogg til log-kanal — aldri blandet
- `!testdeadline` fjernet, `!sync` erstatter den

### v2.0 — Multi-server refaktorering (mars 2026)
- Full omskriving fra enkeltserver til multi-server via `servers.json`
- `discord.ext.tasks` erstatter alle cron-jobber og Cloud Scheduler
- To-kanal-modell per server: nyhetskanal og log-kanal
- GCS-persistens for deduplisering av poster på tvers av restarter
- Deployment til Google Cloud Run

### v1.1 — Bootstrap-diff og caching (mai–juli 2025)
- `bootstrap_diff.py` integrert — oppdager prisendringer og skader automatisk
- Lokal filcache med TTL for å redusere API-kall
- `servers.json` lagt til for server/liga-konfigurasjon
- Diverse bugfikser i cache-håndtering og logging

### v1.0 — Initial (mai 2025)
- Grunnleggende Fantasy-bot med Discord webhook
- Runde-info, spillerdata og drømmeteam fra Eliteserien Fantasy API
- Deadline-påminnelser og rundesummering
