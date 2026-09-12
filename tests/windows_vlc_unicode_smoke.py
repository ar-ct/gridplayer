"""Windows-only smoke test for bundled libVLC media paths and filters."""

import ctypes
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path


class _ModuleDescription(ctypes.Structure):
    pass


_ModuleDescriptionPtr = ctypes.POINTER(_ModuleDescription)
_ModuleDescription._fields_ = [
    ("psz_name", ctypes.c_char_p),
    ("psz_shortname", ctypes.c_char_p),
    ("psz_longname", ctypes.c_char_p),
    ("psz_help", ctypes.c_char_p),
    ("p_next", _ModuleDescriptionPtr),
]


def _make_test_wav(root: Path) -> Path:
    # Every component is legal on Windows; the combined path is deliberately
    # longer than the historical MAX_PATH (260 chars).
    directory = (
        root
        / ("Видео_" + "Ж" * 70)
        / ("Mixed-Кириллица-Latin_" + "я" * 70)
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (
        "Реальный media test 🎬 [2026] # & + = ! @ $ (final) _ "
        + "LongName_" * 12
        + "Ёё.wav"
    )

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000)

    if len(str(path)) <= 260:
        raise AssertionError(f"Test path is not long enough: {len(str(path))}")

    return path


def _configure_libvlc(libvlc):
    libvlc.libvlc_new.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
    libvlc.libvlc_new.restype = ctypes.c_void_p
    libvlc.libvlc_release.argtypes = [ctypes.c_void_p]

    libvlc.libvlc_media_new_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    libvlc.libvlc_media_new_path.restype = ctypes.c_void_p
    libvlc.libvlc_media_release.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_parse.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_get_duration.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_get_duration.restype = ctypes.c_longlong

    libvlc.libvlc_video_filter_list_get.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_video_filter_list_get.restype = _ModuleDescriptionPtr
    libvlc.libvlc_module_description_list_release.argtypes = [_ModuleDescriptionPtr]


def _video_filter_names(libvlc, instance) -> set[str]:
    head = libvlc.libvlc_video_filter_list_get(instance)
    if not head:
        raise RuntimeError("libvlc_video_filter_list_get returned NULL")

    names = set()
    try:
        current = head
        while current:
            name = current.contents.psz_name
            if name:
                names.add(name.decode("utf-8", errors="replace"))
            current = current.contents.p_next
    finally:
        libvlc.libvlc_module_description_list_release(head)

    return names


def _parse_with_libvlc(libvlc_dir: Path, media_path: Path) -> tuple[int, set[str]]:
    os.environ["VLC_PLUGIN_PATH"] = str(libvlc_dir / "plugins")
    dll_handle = os.add_dll_directory(str(libvlc_dir))
    try:
        libvlc = ctypes.CDLL(str(libvlc_dir / "libvlc.dll"))
        _configure_libvlc(libvlc)

        instance = libvlc.libvlc_new(0, None)
        if not instance:
            raise RuntimeError("libvlc_new returned NULL")

        try:
            filter_names = _video_filter_names(libvlc, instance)
            media = libvlc.libvlc_media_new_path(
                instance, str(media_path).encode("utf-8")
            )
            if not media:
                raise RuntimeError("libvlc_media_new_path returned NULL")

            try:
                libvlc.libvlc_media_parse(media)
                duration = int(libvlc.libvlc_media_get_duration(media))
                return duration, filter_names
            finally:
                libvlc.libvlc_media_release(media)
        finally:
            libvlc.libvlc_release(instance)
    finally:
        dll_handle.close()


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This smoke test must run on Windows")
    if len(sys.argv) != 2:
        raise RuntimeError("Usage: windows_vlc_unicode_smoke.py <libVLC directory>")

    libvlc_dir = Path(sys.argv[1]).resolve()
    if not (libvlc_dir / "libvlc.dll").is_file():
        raise FileNotFoundError(libvlc_dir / "libvlc.dll")

    video_filter_dir = libvlc_dir / "plugins" / "video_filter"
    required_plugins = {
        "sharpen": video_filter_dir / "libsharpen_plugin.dll",
        "adjust": video_filter_dir / "libadjust_plugin.dll",
    }
    for plugin_path in required_plugins.values():
        if not plugin_path.is_file():
            raise FileNotFoundError(plugin_path)

    test_root = Path(tempfile.gettempdir()) / "gridplayer-vlc-unicode-smoke"
    shutil.rmtree(test_root, ignore_errors=True)
    try:
        media_path = _make_test_wav(test_root)
        duration, filter_names = _parse_with_libvlc(libvlc_dir, media_path)
        if duration <= 0:
            raise AssertionError(
                f"Bundled libVLC did not parse the test media; duration={duration}"
            )

        missing_filters = required_plugins.keys() - filter_names
        if missing_filters:
            raise AssertionError(
                f"Bundled libVLC does not expose filters: {sorted(missing_filters)}"
            )

        print(f"Bundled libVLC parsed Unicode long path ({len(str(media_path))} chars)")
        print(f"Parsed duration: {duration} ms")
        print("Bundled libVLC exposes sharpen and adjust video filters")
        return 0
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
