from pathlib import Path

import pytest

from poker_fate_strategy_research.assets import asset_path


def test_asset_path_preserves_distinct_container_paths(tmp_path: Path) -> None:
    engine = asset_path(tmp_path, 'src/engine/init.lua')
    interface = asset_path(tmp_path, 'src/ui/init.lua')
    assert engine == tmp_path / 'src/engine/init.lua'
    assert interface == tmp_path / 'src/ui/init.lua'
    assert engine != interface


@pytest.mark.parametrize(
    'name', ['/absolute.lua', '../outside.lua', 'src/../../out', '.']
)
def test_asset_path_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match='Unsafe asset name'):
        asset_path(tmp_path, name)


def test_asset_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / 'sources'
    root.mkdir()
    (root / 'linked').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes output directory'):
        asset_path(root, 'linked/out.lua')
