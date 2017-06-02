from abcmd.utils import  parse_args, log_error_and_exit


import pytest


@pytest.mark.parametrize('error', (
    TypeError('error message'),
    'error message',
    'error: message'
))
def test_log_error_and_exit(error, mocker):
    exit_mock = mocker.patch('abcmd.utils.sys.exit')
    logging_mock = mocker.patch('abcmd.logging.error')

    log_error_and_exit(error)

    assert logging_mock.called
    assert exit_mock.called


@pytest.mark.parametrize('cmd, expected', (
    ('testtask -c test_configpath --dry-run',
     {'task': 'testtask', 'configpath': 'test_configpath', 'dry_run': True}),
    ('testtask',
     {'task': 'testtask', 'configpath': '/tmp', 'dry_run': False}),
    ('', {})
))
def test_parse_args(cmd, expected):
    if not cmd:
        with pytest.raises(SystemExit):
            args = parse_args(cmd.split(), confdir='/tmp')
    else:
        args = parse_args(cmd.split(), confdir='/tmp')
        assert vars(args) == expected
