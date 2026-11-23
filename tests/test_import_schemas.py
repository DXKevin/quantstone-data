from quantstone_data.import_schemas import ImportJobCreate


def test_directory_import_purpose_defaults_to_initial_and_accepts_repair() -> None:
    common = {
        "dataset_id": "demo.cn.stock.tick",
        "scanner_key": "demo",
        "operation": "import_tick",
        "source_root": "/data/imports/demo",
    }

    assert ImportJobCreate(**common).purpose.value == "initial"
    assert ImportJobCreate(**common, purpose="repair").purpose.value == "repair"
