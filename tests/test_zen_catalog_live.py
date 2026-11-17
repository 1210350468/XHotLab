import asyncio

import pytest

from app import zen
from app.agent_worker import available, validate_workdir
from app.config import ROOT


def test_live_model_catalog_and_prices():
    catalog = asyncio.run(zen.refresh_catalog())
    assert catalog['total'] >= 50
    assert catalog['source'] == zen.MODEL_URL
    assert len({model['id'] for model in catalog['models']}) == catalog['total']
    models = {model['id']: model for model in catalog['models']}
    assert 'glm-5.3-flash' in models
    assert models['glm-5.3-flash']['input_price'] > 0
    assert models['glm-5.3-flash']['output_price'] > 0
    assert 'low' in models['glm-5.3-flash']['efforts']
    assert 'high' in models['glm-5.3-flash']['efforts']
    assert len({model['native_api'] for model in models.values()}) >= 3


def test_model_settings_validate_official_capabilities():
    current = zen.settings()
    with pytest.raises(ValueError):
        zen.update_settings({'compose_model': 'unlisted-model-id'})
    assert zen.settings()['compose_model'] == current['compose_model']
    with pytest.raises(ValueError):
        zen.update_settings({'compose_effort': 'invalid-effort'})


def test_harness_workdir_and_installed_tools():
    assert validate_workdir(str(ROOT)) == ROOT.resolve()
    assert available()['codex']
    assert available()['claude']
    with pytest.raises(ValueError):
        validate_workdir('C:/Windows')
