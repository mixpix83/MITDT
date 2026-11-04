# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp>=1.2,<2",
#     "garmin-connect-personal-api-python",
# ]
# ///
"""Server MCP per leggere i propri dati Garmin Connect tramite la Personal API.

Avvio:  uv run --script server.py

La chiave Personal API viene letta (in quest'ordine) da:
  1. variabile d'ambiente GARMIN_PERSONAL_API_KEY
  2. file ~/.config/garmin/connect-personal-api-key  (consigliato, chmod 600)

Il token OAuth2 (valido 24 h) viene ottenuto e rinnovato automaticamente e
salvato in cache in ~/.config/garmin/connect-personal-api-bearer-token.json.
Tutti gli strumenti sono in sola lettura.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from garmin_personal_api import (
    GarminPersonalApiClient,
    GarminPersonalApiError,
    HttpError,
    PersonalApiAuthenticator,
    resolve_api_key,
)
from mcp.server.fastmcp import FastMCP

# Su stdio i log devono andare su stderr, mai su stdout.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

MAX_RESPONSE_CHARS = 60_000

mcp = FastMCP(
    "garmin",
    instructions=(
        "Accesso in sola lettura ai dati Garmin Connect dell'utente (attività, sonno, HRV, "
        "Body Battery, stress, passi, frequenza cardiaca, peso). Le date sono nel formato "
        "YYYY-MM-DD; se omesse si usa oggi. Per gli intervalli preferisci gli strumenti "
        "*_range / *_summaries invece di chiamare più volte lo strumento giornaliero."
    ),
)


def _today() -> str:
    return date.today().isoformat()


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _call(fn: Callable[[GarminPersonalApiClient], Any]) -> str:
    """Esegue una richiesta autenticata, rinnovando il token una volta se scaduto/revocato."""
    try:
        api_key = resolve_api_key()
    except (GarminPersonalApiError, OSError) as exc:
        return (
            "Chiave Garmin Personal API non trovata. Salvala in "
            "~/.config/garmin/connect-personal-api-key (chmod 600) oppure nella variabile "
            f"d'ambiente GARMIN_PERSONAL_API_KEY. Dettaglio: {exc}"
        )

    try:
        with PersonalApiAuthenticator() as auth:
            token = auth.obtain_token(api_key)
            with GarminPersonalApiClient(token.access_token) as client:
                try:
                    result = fn(client)
                except HttpError as exc:
                    if exc.status_code != 401:
                        raise
                    token = auth.obtain_token(api_key, force_refresh=True)
                    client.update_bearer_token(token.access_token)
                    result = fn(client)
    except HttpError as exc:
        hint = ""
        if exc.status_code in (401, 403):
            hint = " La chiave potrebbe essere scaduta o revocata: creane una nuova su Garmin Connect."
        return f"Errore Garmin HTTP {exc.status_code}: {exc.response_text[:500]}{hint}"
    except GarminPersonalApiError as exc:
        return f"Errore Garmin: {exc}"

    if result is None:
        return "Nessun dato per il periodo richiesto."
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_RESPONSE_CHARS:
        text = (
            text[:MAX_RESPONSE_CHARS]
            + f"\n…[risposta troncata: {len(text)} caratteri totali; restringi l'intervallo]"
        )
    return text


# --- Profilo ---------------------------------------------------------------


@mcp.tool()
def profilo() -> str:
    """Impostazioni del profilo utente Garmin (unità di misura, dati fisici, preferenze)."""
    return _call(lambda c: c.get_user_profile_settings())


@mcp.tool()
def zone_frequenza_cardiaca() -> str:
    """Zone di frequenza cardiaca configurate per sport."""
    return _call(lambda c: c.get_heart_rate_zones())


@mcp.tool()
def eta_fitness(data: str | None = None) -> str:
    """Età fitness Garmin alla data indicata (YYYY-MM-DD, default oggi)."""
    return _call(lambda c: c.get_fitness_age(data or _today()))


# --- Attività ----------------------------------------------------------------


@mcp.tool()
def cerca_attivita(
    data_inizio: str | None = None,
    data_fine: str | None = None,
    tipo_attivita: str | None = None,
    limite: int = 20,
    offset: int = 0,
) -> str:
    """Elenco riassuntivo delle attività (corse, bici, nuoto, palestra…).

    data_inizio/data_fine: YYYY-MM-DD (facoltative). tipo_attivita: chiave Garmin,
    es. "running", "cycling", "swimming", "strength_training". limite max consigliato 50.
    """
    return _call(
        lambda c: c.search_activities(
            start=offset,
            limit=max(1, min(limite, 100)),
            start_date=data_inizio,
            end_date=data_fine,
            activity_type=tipo_attivita,
        )
    )


@mcp.tool()
def dettaglio_attivita(activity_id: int) -> str:
    """Dettaglio completo di una singola attività (usa l'activityId da cerca_attivita)."""
    return _call(lambda c: c.get_activity(activity_id))


@mcp.tool()
def allenamento_attivita(activity_id: int) -> str:
    """Allenamento strutturato (workout) associato a un'attività, se presente."""
    return _call(lambda c: c.get_activity_workouts(activity_id))


# --- Riepiloghi giornalieri --------------------------------------------------


@mcp.tool()
def riepilogo_giornaliero(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Riepilogo giornaliero (passi, calorie, FC a riposo, stress, intensità…) per un intervallo.

    Default: ultimi 7 giorni.
    """
    return _call(
        lambda c: c.get_daily_summaries(data_inizio or _days_ago(6), data_fine or _today())
    )


@mcp.tool()
def passi(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Passi giornalieri per un intervallo (default ultimi 7 giorni)."""
    return _call(lambda c: c.get_daily_steps(data_inizio or _days_ago(6), data_fine or _today()))


@mcp.tool()
def stress(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Stress medio giornaliero per un intervallo (default ultimi 7 giorni)."""
    return _call(lambda c: c.get_daily_stress(data_inizio or _days_ago(6), data_fine or _today()))


@mcp.tool()
def body_battery(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Body Battery giornaliera (carica/scarica) per un intervallo (default ultimi 7 giorni)."""
    return _call(
        lambda c: c.get_daily_body_battery(data_inizio or _days_ago(6), data_fine or _today())
    )


@mcp.tool()
def idratazione(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Idratazione giornaliera registrata (default ultimi 7 giorni)."""
    return _call(
        lambda c: c.get_daily_hydration(data_inizio or _days_ago(6), data_fine or _today())
    )


@mcp.tool()
def riepilogo_attivita_benessere(
    data_inizio: str | None = None, data_fine: str | None = None
) -> str:
    """Riepilogo delle attività di benessere (minuti di intensità ecc.), default ultimi 7 giorni."""
    return _call(
        lambda c: c.get_wellness_activity_summaries(
            data_inizio or _days_ago(6), data_fine or _today()
        )
    )


# --- Sonno, HRV, cuore -------------------------------------------------------


@mcp.tool()
def sonno(data: str | None = None) -> str:
    """Dettaglio del sonno di una notte (fasi, punteggio, FC, respirazione). Default: oggi."""
    return _call(lambda c: c.get_daily_sleep(data or _today()))


@mcp.tool()
def sonno_intervallo(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Riepiloghi del sonno per più notti (default ultimi 7 giorni)."""
    return _call(
        lambda c: c.get_daily_sleep_summaries(data_inizio or _days_ago(6), data_fine or _today())
    )


@mcp.tool()
def hrv(data: str | None = None) -> str:
    """Variabilità della frequenza cardiaca (HRV) notturna di un giorno. Default: oggi."""
    return _call(lambda c: c.get_daily_hrv(data or _today()))


@mcp.tool()
def hrv_intervallo(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Riepiloghi HRV giornalieri per un intervallo (default ultimi 7 giorni)."""
    return _call(
        lambda c: c.get_daily_hrv_summaries(data_inizio or _days_ago(6), data_fine or _today())
    )


@mcp.tool()
def frequenza_cardiaca(data: str | None = None) -> str:
    """Frequenza cardiaca del giorno (min, max, a riposo e campioni). Default: oggi."""
    return _call(lambda c: c.get_daily_heart_rate(data or _today()))


@mcp.tool()
def spo2(data: str | None = None) -> str:
    """Saturazione di ossigeno (SpO2) del giorno. Default: oggi."""
    return _call(lambda c: c.get_daily_spo2(data or _today()))


# --- Peso e alimentazione ----------------------------------------------------


@mcp.tool()
def peso(data_inizio: str | None = None, data_fine: str | None = None) -> str:
    """Misurazioni del peso e composizione corporea (default ultimi 30 giorni)."""
    return _call(
        lambda c: c.get_weight_measurements(data_inizio or _days_ago(29), data_fine or _today())
    )


@mcp.tool()
def diario_alimentare(data: str | None = None) -> str:
    """Diario alimentare registrato su Garmin Connect per un giorno. Default: oggi."""
    return _call(lambda c: c.get_daily_food_logs(data or _today()))


# --- Accesso generico ----------------------------------------------------------


@mcp.tool()
def garmin_get(percorso: str, parametri: dict[str, str] | None = None) -> str:
    """Chiamata GET generica a un endpoint della Garmin Personal API senza strumento dedicato.

    percorso: es. "/periodichealth-service/menstrualcycle/summary/2026-11-01".
    Vedi https://developer.garmin.com/gc-developer-program/personal/swagger-docs/
    """
    if not percorso.startswith("/") or "://" in percorso or ".." in percorso:
        return "Percorso non valido: deve iniziare con '/' ed essere relativo all'API Garmin."
    return _call(lambda c: c.get(percorso, params=parametri or None))


if __name__ == "__main__":
    mcp.run()
