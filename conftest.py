import os 
import tempfile

import pytest


@pytest.fixture(params=[
    ('yaml', '---\ntest_entry: ok'),
    ('toml', 'test_entry = "ok"\n'),
])
def config_file(request):
    extension, text = request.param
    with tempfile.NamedTemporaryFile(suffix='.' + extension) as config:
        task = os.path.splitext(os.path.basename(config.name))[0]
        config.write(text.encode())
        config.seek(0)
        yield {'task': task, 'path': os.path.dirname(config.name),
               'file': config.name, 'loader': extension}
