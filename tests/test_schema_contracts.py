import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_codex_patch_result_schema_is_strict_output_compatible():
    schema = json.loads((REPO / "src/faultline/harden/patch_result.schema.json").read_text())

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_public_and_packaged_patch_result_schemas_match():
    public = json.loads((REPO / "schemas/patch_result.schema.json").read_text())
    packaged = json.loads((REPO / "src/faultline/harden/patch_result.schema.json").read_text())

    assert public == packaged


def test_public_contract_schemas_are_well_formed():
    schemas = sorted((REPO / "schemas").glob("*.schema.json"))
    ids = []
    for path in schemas:
        schema = json.loads(path.read_text())
        ids.append(schema["$id"])
        assert set(schema["required"]).issubset(schema["properties"])

    assert len(ids) == len(set(ids))
    assert {path.stem.removesuffix(".schema") for path in schemas} == {
        "attack_plan",
        "dossier",
        "fault_schedule",
        "patch_result",
        "run_record",
    }
