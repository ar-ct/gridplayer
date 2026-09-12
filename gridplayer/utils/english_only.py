def remove_language_settings_ui(dialog) -> None:
    """Remove the language selector from the already-built Settings dialog."""
    dialog.settings_map.pop("player/language", None)

    language_page = dialog.page_general_language
    dialog.section_page.removeWidget(language_page)
    language_page.hide()
    language_page.setParent(None)
    language_page.deleteLater()

    for row in range(dialog.section_index.count()):
        item = dialog.section_index.item(row)
        if item.text() == "Language":
            dialog.section_index.takeItem(row)
            break
