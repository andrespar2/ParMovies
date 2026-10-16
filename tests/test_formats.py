"""Pruebas de seleccion de calidad, audio y subtitulos."""

from __future__ import annotations

from parmovies.api.models import MediaVariant, SubtitleTrack
from parmovies.media import formats


def _variants():
    return [
        MediaVariant(url="480", height=480, bandwidth=600_000),
        MediaVariant(url="720", height=720, bandwidth=1_600_000),
        MediaVariant(url="1080", height=1080, bandwidth=3_000_000),
    ]


def test_pick_best():
    assert formats.pick_variant(_variants(), "best").height == 1080


def test_pick_exacto():
    assert formats.pick_variant(_variants(), 720).height == 720
    assert formats.pick_variant(_variants(), "720p").height == 720


def test_pick_inferior_cuando_no_existe():
    # No debe simular 2160p: baja al mayor disponible por debajo.
    assert formats.pick_variant(_variants(), 2160).height == 1080


def test_pick_menor_si_todo_es_mayor():
    vs = [MediaVariant(url="x", height=720, bandwidth=1)]
    assert formats.pick_variant(vs, 480).height == 720


def test_sin_variantes():
    assert formats.pick_variant([], "best") is None


def test_available_heights():
    assert formats.available_heights(_variants()) == [1080, 720, 480]


def test_spanish_kind():
    assert formats.spanish_kind("Latino - Ingl\u00e9s") == "latino"
    assert formats.spanish_kind("Espa\u00f1ol Latino") == "latino"
    assert formats.spanish_kind("Espa\u00f1ol de Espa\u00f1a") == "espana"
    assert formats.spanish_kind("castellano") == "espana"
    assert formats.spanish_kind("Spanish") == "generico"
    assert formats.spanish_kind("English") is None


def test_audio_rank_prioriza_latino():
    labels = ["Ingl\u00e9s", "Espa\u00f1ol Espa\u00f1a", "Espa\u00f1ol Latino", "Portugu\u00e9s"]
    ordered = formats.order_audio_labels(labels)
    assert ordered[0] == "Espa\u00f1ol Latino"
    assert ordered[1] == "Espa\u00f1ol Espa\u00f1a"


def test_preferred_audio_index():
    labels = ["Ingl\u00e9s", "Espa\u00f1ol Latino"]
    assert formats.preferred_audio_index(labels) == 1


def test_preferred_audio_con_original():
    labels = ["Franc\u00e9s", "Ingl\u00e9s", "Espa\u00f1ol"]
    assert formats.preferred_audio_index(labels, original_language="en") == 2


def test_subtitle_modos():
    tracks = [
        SubtitleTrack(label="English", language="en"),
        SubtitleTrack(label="Spanish", language="es"),
        SubtitleTrack(label="Espa\u00f1ol Latino", language="es-419"),
    ]
    assert [t.label for t in formats.select_subtitles(tracks, "spanish")] == [
        "Espa\u00f1ol Latino",
        "Spanish",
    ]
    assert len(formats.select_subtitles(tracks, "all")) == 3
    assert formats.select_subtitles(tracks, "none") == []
    assert [t.label for t in formats.select_subtitles(tracks, "manual", manual_indices=[0])] == [
        "English"
    ]


def test_subtitle_rank_ingles():
    assert formats.subtitle_rank("en") == 3
    assert formats.subtitle_rank("es-419") == 0
