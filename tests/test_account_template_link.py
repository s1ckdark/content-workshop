import json

import cache
from cache import add_account, get_accounts, update_account


def test_update_account_merges_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "get_cache_path", lambda: str(tmp_path))
    add_account("youtube", {"id": "a1", "nickname": "n", "videos": []})
    add_account("youtube", {"id": "a2", "nickname": "m", "videos": []})

    assert update_account("youtube", "a2", {"template_id": "t1"}) is True
    assert update_account("youtube", "missing", {"template_id": "t1"}) is False

    accounts = {a["id"]: a for a in get_accounts("youtube")}
    assert accounts["a2"]["template_id"] == "t1"
    assert accounts["a2"]["nickname"] == "m"
    assert "template_id" not in accounts["a1"]
    assert json.loads((tmp_path / "youtube.json").read_text())["accounts"][1]["template_id"] == "t1"
