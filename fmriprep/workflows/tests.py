"""Utilities and mocks for testing and documentation building."""
from pathlib import Path
from pkg_resources import resource_filename as pkgrf
from toml import loads
from tempfile import mkdtemp


def mock_config(return_bold=False):
    """Create a mock config for documentation and testing purposes."""
    from .. import config
    filename = Path(pkgrf('fmriprep', 'data/tests/config.toml'))
    settings = loads(filename.read_text())
    for sectionname, configs in settings.items():
        if sectionname != 'environment':
            section = getattr(config, sectionname)
            section.load(configs)
    config.set_logger_level()
    config.init_spaces()

    config.execution.work_dir = Path(mkdtemp())
    config.execution.bids_dir = Path(pkgrf('fmriprep', 'data/tests/ds000005'))
    config.init_layout()

    if return_bold:
        return config.execution.layout.get(suffix='bold', return_type='file')[0]