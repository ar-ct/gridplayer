from types import SimpleNamespace

import gridplayer.vlc_player.player_base as player_base


class _FakeSettings:
    def sync_get(self, key):
        assert key == "player/video_init_timeout"
        return 10


class _FakeLog:
    def info(self, message):
        self.last_info = message

    def debug(self, message):
        self.last_debug = message


class _FakeMedia:
    def add_options(self, *options):
        self.options = options


class _FakeInstance:
    def __init__(self):
        self.received_path = None

    def media_new_path(self, path):
        self.received_path = path
        return _FakeMedia()


class _FakeEventManager:
    def attach_to_media(self, media):
        self.media = media


def test_local_unicode_path_is_forwarded_to_libvlc_without_reencoding(monkeypatch):
    monkeypatch.setattr(player_base, "Settings", lambda: _FakeSettings())

    path = (
        "C:\\Видео архив\\Папка с пробелами\\Mixed-Кириллица-Latin\\"
        "очень длинное имя 🎬 [2026] # & + = ! @ $ (final) Ёё.MP4"
    )
    instance = _FakeInstance()
    driver = SimpleNamespace(
        instance=instance,
        _log=_FakeLog(),
        _media_options=[],
        _event_manager=_FakeEventManager(),
        is_preparse_required=False,
        loopback_load_video_st2_set_media=lambda: None,
        error=lambda message: None,
    )
    media_input = SimpleNamespace(
        uri=path,
        is_live=False,
        is_audio_only=False,
        video=SimpleNamespace(is_paused=False),
    )

    player_base.VlcPlayerBase.load_video(driver, media_input)

    assert instance.received_path == path
    assert driver.media_input.uri == path
