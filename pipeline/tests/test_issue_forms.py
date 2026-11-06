"""The repo's GitHub issue forms, which the site's feedback links point to."""

from pathlib import Path

FORMS = Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE"


def test_there_is_a_feature_request_form_and_a_data_error_form():
    names = sorted(p.name for p in FORMS.glob("*.yml"))
    assert names == ["config.yml", "data_error.yml", "feature_request.yml"]


def test_each_form_has_a_name_a_description_a_label_and_a_body():
    for name in ("data_error.yml", "feature_request.yml"):
        text = (FORMS / name).read_text()
        for key in ("name:", "description:", "labels:", "body:", "type: textarea"):
            assert key in text, f"{name} has no {key}"
        assert "\t" not in text, f"{name} has a tab, which YAML doesn't allow"


def test_a_data_error_asks_which_page_and_what_looks_wrong():
    text = (FORMS / "data_error.yml").read_text()
    assert "id: page" in text
    assert "id: problem" in text


def test_the_chooser_offers_email_for_people_without_github():
    text = (FORMS / "config.yml").read_text()
    assert "contact_links:" in text
    assert "url: https://gerrymandermap.us/methodology#feedback" in text
    assert "hello@gerrymandermap.us" in text


def test_forms_use_labels_the_repo_already_has():
    # GitHub silently skips a label that doesn't exist in the repo.
    assert 'labels: ["bug"]' in (FORMS / "data_error.yml").read_text()
    assert 'labels: ["enhancement"]' in (FORMS / "feature_request.yml").read_text()
