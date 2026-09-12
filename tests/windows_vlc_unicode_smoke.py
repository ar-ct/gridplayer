"""Windows-only smoke tests for bundled libVLC paths and video-filter output."""

import ctypes
import os
import shutil
import struct
import sys
import tempfile
import time
import wave
from ctypes import wintypes
from pathlib import Path

from PyQt5.QtGui import QImage


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


def _make_color_bmp(path: Path, width=160, height=120) -> Path:
    """Create a vivid uncompressed 24-bit BMP without external codecs."""
    row_stride = (width * 3 + 3) & ~3
    pixel_size = row_stride * height
    file_size = 54 + pixel_size

    header = bytearray()
    header += b"BM"
    header += struct.pack("<IHHI", file_size, 0, 0, 54)
    header += struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height,
        1,
        24,
        0,
        pixel_size,
        2835,
        2835,
        0,
        0,
    )

    pixels = bytearray()
    padding = b"\x00" * (row_stride - width * 3)
    for y in range(height):
        for x in range(width):
            # Strong color and luminance variation makes an all-black output
            # unambiguous even after contrast/saturation/sharpen processing.
            checker = ((x // 20) + (y // 20)) % 2
            if checker:
                r = 235
                g = 45 + (y * 160 // max(height - 1, 1))
                b = 35
            else:
                r = 25
                g = 70
                b = 220 - (x * 120 // max(width - 1, 1))
            pixels.extend((b, g, r))
        pixels.extend(padding)

    path.write_bytes(header + pixels)
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
    libvlc.libvlc_media_add_option.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    libvlc.libvlc_media_player_new.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_player_new.restype = ctypes.c_void_p
    libvlc.libvlc_media_player_release.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_player_set_media.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libvlc.libvlc_media_player_set_hwnd.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libvlc.libvlc_media_player_play.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_player_play.restype = ctypes.c_int
    libvlc.libvlc_media_player_stop.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_player_has_vout.argtypes = [ctypes.c_void_p]
    libvlc.libvlc_media_player_has_vout.restype = ctypes.c_uint
    libvlc.libvlc_video_take_snapshot.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_char_p,
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    libvlc.libvlc_video_take_snapshot.restype = ctypes.c_int

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


def _load_libvlc(libvlc_dir: Path):
    os.environ["VLC_PLUGIN_PATH"] = str(libvlc_dir / "plugins")
    dll_handle = os.add_dll_directory(str(libvlc_dir))
    libvlc = ctypes.CDLL(str(libvlc_dir / "libvlc.dll"))
    _configure_libvlc(libvlc)
    return libvlc, dll_handle


def _parse_with_libvlc(libvlc_dir: Path, media_path: Path) -> tuple[int, set[str]]:
    libvlc, dll_handle = _load_libvlc(libvlc_dir)
    try:
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


def _create_test_window():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND

    hwnd = user32.CreateWindowExW(
        0,
        "STATIC",
        "GridPlayer VLC filter smoke",
        0x00CF0000,
        0,
        0,
        320,
        240,
        None,
        None,
        kernel32.GetModuleHandleW(None),
        None,
    )
    if not hwnd:
        raise ctypes.WinError()

    user32.ShowWindow(hwnd, 5)
    user32.UpdateWindow(hwnd)
    return hwnd


def _pump_windows_messages():
    user32 = ctypes.windll.user32
    msg = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def _wait_for_vout(libvlc, player, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _pump_windows_messages()
        if libvlc.libvlc_media_player_has_vout(player) > 0:
            return
        time.sleep(0.05)
    raise TimeoutError("libVLC did not create a video output")


def _mean_rgb(path: Path) -> float:
    image = QImage(str(path))
    if image.isNull():
        raise AssertionError(f"Qt could not decode VLC snapshot: {path}")

    image = image.convertToFormat(QImage.Format_RGB32)
    step_x = max(image.width() // 40, 1)
    step_y = max(image.height() // 30, 1)
    total = 0
    samples = 0
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            pixel = image.pixel(x, y)
            total += (pixel >> 16) & 0xFF
            total += (pixel >> 8) & 0xFF
            total += pixel & 0xFF
            samples += 3

    return total / samples


def _render_filter_chain(
    libvlc_dir: Path, media_path: Path, output_path: Path, filter_chain: str
) -> float:
    libvlc, dll_handle = _load_libvlc(libvlc_dir)
    hwnd = None
    instance = None
    player = None
    media = None
    try:
        args = [
            b"--no-audio",
            b"--no-video-title-show",
            f"--video-filter={filter_chain}".encode(),
        ]
        argv = (ctypes.c_char_p * len(args))(*args)
        instance = libvlc.libvlc_new(len(args), argv)
        if not instance:
            raise RuntimeError("libvlc_new returned NULL for visual filter test")

        player = libvlc.libvlc_media_player_new(instance)
        if not player:
            raise RuntimeError("libvlc_media_player_new returned NULL")

        hwnd = _create_test_window()
        libvlc.libvlc_media_player_set_hwnd(player, ctypes.c_void_p(hwnd))

        media = libvlc.libvlc_media_new_path(instance, str(media_path).encode("utf-8"))
        if not media:
            raise RuntimeError("libvlc_media_new_path returned NULL for BMP")
        libvlc.libvlc_media_add_option(media, b":image-duration=5")
        libvlc.libvlc_media_player_set_media(player, media)

        if libvlc.libvlc_media_player_play(player) == -1:
            raise RuntimeError(f"Failed to play visual test with {filter_chain}")

        _wait_for_vout(libvlc, player)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            _pump_windows_messages()
            time.sleep(0.02)

        snapshot_result = libvlc.libvlc_video_take_snapshot(
            player, 0, str(output_path).encode("utf-8"), 0, 0
        )
        if snapshot_result != 0:
            raise AssertionError(
                f"libVLC snapshot failed for filter chain {filter_chain!r}"
            )

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not output_path.is_file():
            _pump_windows_messages()
            time.sleep(0.05)
        if not output_path.is_file():
            raise TimeoutError(f"Snapshot was not written for {filter_chain!r}")

        mean_rgb = _mean_rgb(output_path)
        if mean_rgb < 10.0:
            raise AssertionError(
                f"Filter chain rendered an effectively black frame: "
                f"{filter_chain!r}, mean RGB={mean_rgb:.2f}"
            )
        return mean_rgb
    finally:
        if player:
            libvlc.libvlc_media_player_stop(player)
            libvlc.libvlc_media_player_release(player)
        if media:
            libvlc.libvlc_media_release(media)
        if instance:
            libvlc.libvlc_release(instance)
        if hwnd:
            ctypes.windll.user32.DestroyWindow(hwnd)
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
    test_root.mkdir(parents=True)
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

        color_bmp = _make_color_bmp(test_root / "filter-input.bmp")
        combinations = {
            "sharpen+contrast": (
                "sharpen{sigma=0.12}:adjust{contrast=1.20,saturation=1.00}"
            ),
            "sharpen+saturation": (
                "sharpen{sigma=0.12}:adjust{contrast=1.00,saturation=1.20}"
            ),
            "sharpen+contrast+saturation": (
                "sharpen{sigma=0.12}:adjust{contrast=1.20,saturation=0.80}"
            ),
        }
        visual_results = {}
        for name, chain in combinations.items():
            visual_results[name] = _render_filter_chain(
                libvlc_dir,
                color_bmp,
                test_root / f"{name}.png",
                chain,
            )

        print(f"Bundled libVLC parsed Unicode long path ({len(str(media_path))} chars)")
        print(f"Parsed duration: {duration} ms")
        print("Bundled libVLC exposes sharpen and adjust video filters")
        for name, mean_rgb in visual_results.items():
            print(f"{name}: non-black snapshot, mean RGB={mean_rgb:.2f}")
        return 0
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
