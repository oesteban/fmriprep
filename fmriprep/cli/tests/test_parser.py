"""Test parser."""
import pytest
from ..parser import _build_parser

MIN_ARGS = ['data/', 'out/', 'participant']


@pytest.mark.parametrize('args,code', [
    ([], 2),
    (MIN_ARGS, 2),  # bids_dir does not exist
    (MIN_ARGS + ['--fs-license-file'], 2),
    (MIN_ARGS + ['--fs-license-file', 'fslicense.txt'], 2),
])
def test_parser_errors(args, code):
    """Check behavior of the parser."""
    with pytest.raises(SystemExit) as error:
        _build_parser().parse_args(args)

    assert error.value.code == code


@pytest.mark.parametrize('args', [
    MIN_ARGS,
    MIN_ARGS + ['--fs-license-file'],
])
def test_parser_valid(tmp_path, args):
    """Check valid arguments."""
    datapath = (tmp_path / 'data')
    datapath.mkdir(exist_ok=True)
    args[0] = str(datapath)

    if '--fs-license-file' in args:
        _fs_file = tmp_path / 'license.txt'
        _fs_file.write_text('')
        args.insert(args.index('--fs-license-file') + 1,
                    str(_fs_file.absolute()))

    opts = _build_parser().parse_args(args)

    assert opts.bids_dir == datapath


@pytest.mark.parametrize('argval,gb', [
    ('1G', 1),
    ('1GB', 1),
    ('1000', 1),
    ('1000M', 1),
    ('1000MB', 1),
    ('1T', 1000),
    ('32000', 32),
])
def test_memory_arg(tmp_path, argval, gb):
    """Check the correct parsing of the memory argument."""
    datapath = (tmp_path / 'data')
    datapath.mkdir(exist_ok=True)
    _fs_file = tmp_path / 'license.txt'
    _fs_file.write_text('')

    args = MIN_ARGS + ['--fs-license-file', str(_fs_file)] \
        + ['--mem', argval]
    opts = _build_parser().parse_args(args)

    assert opts.memory_gb == gb
