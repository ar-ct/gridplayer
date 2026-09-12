import csv
from pathlib import Path

import pycountry
import pytest
from PyQt5.QtWidgets import QApplication
from streamlink.utils.l10n import Localization

from gridplayer import settings as settings_module
from gridplayer.dialogs.settings import SettingsDialog
from gridplayer.params.languages import LANGUAGES
from gridplayer.utils.english_only import remove_language_settings_ui


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])

    if settings_module.SETTINGS is not None:
        try:
            settings_module.SETTINGS.settings.fileName()
        except RuntimeError:
            settings_module.SETTINGS = None

    return app


def test_only_english_language_metadata_remains():
    assert [language.code for language in LANGUAGES] == ["en_US"]


def test_old_language_setting_is_forced_to_english(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, "get_app_data_dir", lambda: tmp_path)

    initial = settings_module._Settings()
    initial.settings.setValue("player/language", "ru_RU")
    initial.sync()

    reopened = settings_module._Settings()
    assert reopened.get("player/language") == "en_US"
    assert reopened.settings.value("player/language") == "en_US"


def test_language_selector_is_removed_from_settings_dialog():
    dialog = SettingsDialog(None)
    language_page = dialog.page_general_language

    remove_language_settings_ui(dialog)

    labels = [dialog.section_index.item(i).text() for i in range(dialog.section_index.count())]
    assert "Language" not in labels
    assert dialog.section_page.indexOf(language_page) == -1
    assert "player/language" not in dialog.settings_map


def test_resource_manifest_has_no_translations_and_only_english_flag():
    resources_file = Path("resources/resources.csv")
    with resources_file.open(newline="", encoding="utf-8") as csvfile:
        rows = list(csv.reader(csvfile))

    assert not [row for row in rows if row[0] == "translation"]
    flag_rows = [row for row in rows if row[1].startswith("icons/flags/")]
    assert flag_rows == [["icon", "icons/flags/en_US.svg", "flag_en_US"]]


def test_streamlink_localization_does_not_require_pycountry_gettext_locales(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(pycountry, "LOCALES_DIR", str(tmp_path / "missing-locales"))

    localization = Localization("en_US")
    assert localization.language.name == "English"
    assert localization.country.alpha2 == "US"
