"""Pruebas de los parsers (desofuscador, embed, reproductor y HLS)."""

from __future__ import annotations

from parmovies.analyzers.embed_parser import parse_embed_page
from parmovies.analyzers.js_unpacker import unpack, unpack_program
from parmovies.analyzers.player_parser import parse_player_config
from parmovies.media.hls import parse_master


def test_unpack_basico():
    # '0 1 2' con base 3 y palabras var|foo|bar -> 'var foo bar'
    assert unpack("0 1 2", 3, 3, ["var", "foo", "bar"]) == "var foo bar"


def test_unpack_respeta_palabras_largas():
    assert unpack("0 1 2", 3, 3, ["a", "bb", "ccc"]) == "a bb ccc"


def test_unpack_program_extremo_a_extremo():
    packed = (
        "eval(function(p,a,c,k,e,d){while(c--)if(k[c])p=p.replace(new RegExp('\\\\b'+c.toString(a)+'\\\\b','g'),k[c]);return p}"
        "('0 1 2',3,3,'var|foo|bar'.split('|'),0,{}))"
    )
    assert unpack_program(packed) == "var foo bar"


def test_unpack_sin_bloque():
    assert unpack_program("<html>nada</html>") is None


EMBED_HTML = """
<html><head><title>Pelicula</title></head><body>
<script type="text/json" id="data">
{"backdrop":"/b.jpg","embeds":[{"format":null,"lang":"Latino - Ingl\u00e9s","quality":"Dual 1080p",
"resolution":null,"sala_id":6,"server":"LaMovie","size":null,"subtitle":0,
"url":"https://vimeos.net/embed-abc.html"}],"episode":0,"poster":"/p.jpg","season":0,
"title":"Pelicula Prueba","tmdb_id":264420,"type":"movie"}
</script>
</body></html>
"""


def test_parse_embed_page():
    data = parse_embed_page(EMBED_HTML)
    assert data is not None
    assert data.title == "Pelicula Prueba"
    assert data.content_type == "movie"
    assert data.poster.endswith("/p.jpg")
    assert data.poster.startswith("https://image.tmdb.org/t/p/original")
    assert len(data.embeds) == 1
    assert data.embeds[0].server == "LaMovie"
    assert data.embeds[0].lang == "Latino - Ingl\u00e9s"
    assert data.embeds[0].url == "https://vimeos.net/embed-abc.html"


def test_parse_embed_page_invalido():
    assert parse_embed_page("<html>sin datos</html>") is None


PLAYER_HTML = """
<html><body><script>
var jws={skin:{name:"x"},sources:[{file:"https://cdn.example/master.m3u8?t=1"}],
autostart:false,image:"https://cdn.example/poster.jpg",duration:"5918.14",
tracks:[{file:"https://cdn.example/spa.vtt",label:"Spanish",kind:"captions","default":true},
{file:"/srt/empty.srt",label:"Upload captions",kind:"captions"}],
captions:{userFontScale:1}};window.playerInstance=jwplayer("vplayer").setup(jws);
</script></body></html>
"""


def test_parse_player_config():
    config = parse_player_config(PLAYER_HTML)
    assert config is not None
    assert len(config.sources) == 1
    assert config.sources[0].url == "https://cdn.example/master.m3u8?t=1"
    assert config.image == "https://cdn.example/poster.jpg"
    assert config.duration_seconds == 5918.14
    assert len(config.tracks) == 2
    assert config.tracks[0]["label"] == "Spanish"
    assert config.tracks[0]["default"] is True


MASTER_M3U8 = """#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=662698,RESOLUTION=888x480,FRAME-RATE=60.000,CODECS="avc1.64001f,mp4a.40.2"
https://cdn.example/n/index.m3u8?t=1
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1672984,RESOLUTION=1336x720,FRAME-RATE=60.000,CODECS="avc1.640028,mp4a.40.2"
https://cdn.example/h/index.m3u8?t=1
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aac",NAME="Espanol",LANGUAGE="es",DEFAULT=YES,URI="https://cdn.example/audio/es.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Spanish",LANGUAGE="es",DEFAULT=YES,URI="https://cdn.example/sub/es.vtt"
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=34028,RESOLUTION=888x480,URI="https://cdn.example/n/iframes.m3u8"
"""


def test_parse_master():
    master = parse_master(MASTER_M3U8, base_url="https://cdn.example/master.m3u8")
    assert master.is_master
    assert len(master.variants) == 2  # no cuenta los I-FRAME
    heights = sorted(v.height for v in master.variants)
    assert heights == [480, 720]
    assert master.variants[1].bandwidth == 1672984
    assert len(master.audio_renditions) == 1
    assert master.audio_renditions[0].is_audio_only
    assert len(master.subtitle_renditions) == 1
    assert master.subtitle_renditions[0].language == "es"


def test_parse_master_media_playlist():
    text = "#EXTM3U\n#EXTINF:10,\nseg0.ts\n#EXTINF:10,\nseg1.ts\n"
    master = parse_master(text, base_url="https://cdn.example/media.m3u8")
    assert not master.is_master
    assert len(master.variants) == 1
    assert master.variants[0].url == "https://cdn.example/media.m3u8"
