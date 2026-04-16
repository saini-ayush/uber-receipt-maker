import data_loader


def test_load_templates_returns_seven():
    assert len(data_loader.load_templates()) == 7


def test_templates_have_required_keys():
    required = {"receipt_id", "receipt_date", "rider_name", "vehicle_type",
                "fare", "driver", "pickup", "dropoff"}
    for t in data_loader.load_templates():
        assert required.issubset(t.keys()), f"Missing keys in {t['receipt_id']}"


def test_display_names_are_strings():
    names = data_loader.template_display_names()
    assert len(names) == 7
    assert all(isinstance(n, str) for n in names)


def test_template_by_index_round_trips():
    templates = data_loader.load_templates()
    for i, t in enumerate(templates):
        assert data_loader.template_by_index(i)["receipt_id"] == t["receipt_id"]
