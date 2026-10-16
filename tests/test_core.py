"""Pruebas de configuracion, historial, seguridad y subtitulos."""

from __future__ import annotations

import json

from parmovies.api.models import SubtitleTrack
from parmovies.configuration.settings import AppSettings
from parmovies.history.history_store import HistoryEntry, HistoryStore
from parmovies.security.redaction import mask_secret, redact_text, redact_url
from parmovies.subtitles.subtitle_manager import save_subtitle, vtt_to_srt


# -- Configuracion ---------------------------------------------------------
def test_settings_defaults():
    settings = AppSettings()
    assert settings.output_format == "mkv"
    assert settings.subtitle_mode == "spanish"
    assert settings.resolved_downloads_dir().name == "Descargas"
    assert not settings.is_authenticated()


def test_settings_guardar_y_cargar(tmp_path):
    target = tmp_path / "config.json"
    settings = AppSettings(api_key="clave-secreta-1234", view_key="vista-secreta", retries=5)
    settings.save(target)
    loaded = AppSettings.load(target)
    assert loaded.api_key == "clave-secreta-1234"
    assert loaded.retries == 5


def test_settings_env_override(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    AppSettings(api_key="archivo").save(target)
    monkeypatch.setenv("PARMOVIES_API_KEY", "entorno")
    loaded = AppSettings.load(target)
    assert loaded.api_key == "entorno"


def test_settings_normaliza_valores_invalidos():
    settings = AppSettings(subtitle_mode="raro", output_format="avi", retries=-3, concurrent_downloads=0)
    settings.normalize()
    assert settings.subtitle_mode == "spanish"
    assert settings.output_format == "mkv"
    assert settings.retries == 0
    assert settings.concurrent_downloads == 1


def test_settings_archivo_corrupto(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("{ esto no es json", encoding="utf-8")
    loaded = AppSettings.load(target)
    assert loaded.output_format == "mkv"


def test_settings_enmascara_claves():
    settings = AppSettings(api_key="ak_1234567890", view_key="view_key_abc")
    assert "ak_1234567890" not in settings.masked_api_key()
    assert settings.masked_api_key().endswith("7890")
    assert settings.masked_view_key().endswith("_abc")


# -- Seguridad -------------------------------------------------------------
def test_redact_url_view_key():
    url = "https://vimeus.com/e/movie?tmdb=1&view_key=SECRETO123"
    redacted = redact_url(url)
    assert "SECRETO123" not in redacted
    assert "view_key=" in redacted


def test_redact_text_con_secretos():
    text = "error con clave ak_1234567890 y mas"
    result = redact_text(text, ["ak_1234567890"])
    assert "ak_1234567890" not in result


def test_mask_secret():
    assert mask_secret("") == "(sin definir)"
    assert mask_secret("abc") == "********"
    assert mask_secret("abcdefgh").endswith("efgh")


# -- Historial -------------------------------------------------------------
def test_historial_persistente(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(path)
    store.add(HistoryEntry(title="Pelicula", status="Completado", size_bytes=100))
    recreated = HistoryStore(path)
    assert recreated.count() == 1
    assert recreated.entries[0].title == "Pelicula"


def test_historial_redacta_origen(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(path)
    store.add(HistoryEntry(title="x", source="https://vimeus.com/e/movie?view_key=SECRETO"))
    assert "SECRETO" not in store.entries[0].source


def test_historial_corrupto(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("no es json", encoding="utf-8")
    store = HistoryStore(path)
    assert store.count() == 0


# -- Subtitulos ------------------------------------------------------------
def test_vtt_a_srt():
    vtt = "WEBVTT\n\n00:02.000 --> 00:03.000\nHola\n\n00:04.000 --> 00:05.000\nMundo\n"
    srt = vtt_to_srt(vtt)
    assert "1\n00:00:02,000 --> 00:00:03,000\nHola" in srt
    assert "2\n00:00:04,000 --> 00:00:05,000\nMundo" in srt


def test_vtt_a_srt_formato_largo():
    vtt = "WEBVTT\n\n01:02:03.500 --> 01:02:05.000\nTexto\n"
    srt = vtt_to_srt(vtt)
    assert "01:02:03,500 --> 01:02:05,000" in srt


def test_guardar_subtitulo(tmp_path):
    base = tmp_path / "Pelicula (2025) [1080p].mkv"
    track = SubtitleTrack(url="https://x/a.vtt", label="Español Latino", language="es-419")
    path = save_subtitle(track, "WEBVTT\n\n00:01.000 --> 00:02.000\nHola\n", base)
    assert path is not None
    assert path.name == "Pelicula (2025) [1080p].es-419.srt"
    assert "00:00:01,000" in path.read_text(encoding="utf-8")
