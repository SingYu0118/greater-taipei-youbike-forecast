from youbike_forecast.serving.publish import enrich_official_translations


def test_enrich_official_translations_uses_compound_station_identity() -> None:
    snapshot = {
        "stations": [
            {"source": "taipei", "station_id": "same", "station_name": "台北站"},
            {"source": "new_taipei", "station_id": "same", "station_name": "新北站"},
        ]
    }
    translations = {
        ("taipei", "same"): {
            "station_name_en": "Taipei Station",
            "district_en": "Daan Dist.",
        },
        ("new_taipei", "same"): {
            "station_name_en": "New Taipei Station",
            "district_en": "Banqiao Dist.",
        },
    }

    enrich_official_translations(snapshot, translations)

    assert snapshot["stations"][0]["station_name_en"] == "Taipei Station"
    assert snapshot["stations"][0]["district_en"] == "Daan Dist."
    assert snapshot["stations"][1]["station_name_en"] == "New Taipei Station"
    assert snapshot["stations"][1]["district_en"] == "Banqiao Dist."
