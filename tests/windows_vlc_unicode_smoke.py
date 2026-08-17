"""Windows-only smoke test for the bundled libVLC filesystem path handling."""

import ctypes
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path


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


def _parse_with_libvlc(libvlc_dir: Path, media_path: Path) -> int:
    os.environ["VLC_PLUGIN_PATH"] = str(libvlc_dir / "plugins")
    dll_handle = os.add_dll_directory(str(libvlc_dir))
    try:
        libvlc = ctypes.CDLL(str(libvlc_dir / "libvlc.dll"))

        libvlc.libvlc_new.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
        libvlc.libvlc_new.restype = ctypes.c_void_p
        libvlc.libvlc_release.argtypes = [ctypes.c_void_p]

        libvlc.libvlc_media_new_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        libvlc.libvlc_media_new_path.restype = ctypes.c_void_p
        libvlc.libvlc_media_release.argtypes = [ctypes.c_void_p]
        libvlc.libvlc_media_parse.argtypes = [ctypes.c_void_p]
        libvlc.libvlc_media_get_duration.argtypes = [ctypes.c_void_p]
        libvlc.libvlc_media_get_duration.restype = ctypes.c_longlong

        instance = libvlc.libvlc_new(0, None)
        if not instance:
            raise RuntimeError("libvlc_new returned NULL")

        try:
            media = libvlc.libvlc_media_new_path(
                instance, str(media_path).encode("utf-8")
            )
            if not media:
                raise RuntimeError("libvlc_media_new_path returned NULL")

            try:
                libvlc.libvlc_media_parse(media)
                return int(libvlc.libvlc_media_get_duration(media))
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

    test_root = Path(tempfile.gettempdir()) / "gridplayer-vlc-unicode-smoke"
    shutil.rmtree(test_root, ignore_errors=True)
    try:
        media_path = _make_test_wav(test_root)
        duration = _parse_with_libvlc(libvlc_dir, media_path)
        if duration <= 0:
            raise AssertionError(
                f"Bundled libVLC did not parse the test media; duration={duration}"
            )
        print(f"Bundled libVLC parsed Unicode long path ({len(str(media_path))} chars)")
        print(f"Parsed duration: {duration} ms")
        return 0
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
