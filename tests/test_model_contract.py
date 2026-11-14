import json
import shutil

import pytest

from sonar_app import model_api


def test_bundled_model_manifest_is_valid():
    model = model_api.default_model()
    assert model.id == 'm3_barcellona'
    assert {i['provider'] for i in model.manifest['inputs']} <= set(model_api.KNOWN_PROVIDERS)
    assert callable(model.entrypoint())


def test_manifest_errors_are_reported(tmp_path):
    folder = tmp_path / 'bad'
    shutil.copytree(model_api.default_model().folder, folder)
    manifest = json.loads((folder / 'sonar_model.json').read_text(encoding='utf-8'))
    manifest['styles']['laeq']['colors'] = manifest['styles']['laeq']['colors'][:-1]
    (folder / 'sonar_model.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(model_api.ModelError, match='len\\(colors\\)'):
        model_api.discover(tmp_path)
    manifest['contract'] = 'sonar-model/0'
    (folder / 'sonar_model.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(model_api.ModelError, match='contratto'):
        model_api.discover(tmp_path)


def test_result_validation(tmp_path, model_output):
    model = model_api.default_model()
    result = model_api.validate_result(model, {'outputs': {'h3': model_output, 'strade': model_output}, 'metadata': {'a': 1}}, tmp_path)
    assert result['outputs']['h3'] == model_output and result['metadata'] == {'a': 1}
    with pytest.raises(model_api.ModelError, match='strade'):
        model_api.validate_result(model, {'outputs': {'h3': model_output}}, tmp_path)
    with pytest.raises(model_api.ModelError, match='outputs'):
        model_api.validate_result(model, [], tmp_path)


def test_a_replacement_model_runs_through_the_contract(tmp_path, model_output, square_city):
    """Un modello nuovo (cartella + manifest + run) funziona senza toccare il software."""
    folder = tmp_path / 'models' / 'fake'
    folder.mkdir(parents=True)
    manifest = json.loads((model_api.default_model().folder / 'sonar_model.json').read_text(encoding='utf-8'))
    manifest.update(id='fake', version='0.1', code={}, inputs=[], outputs=[manifest['outputs'][0]])
    (folder / 'sonar_model.json').write_text(json.dumps(manifest), encoding='utf-8')
    (folder / 'adapter.py').write_text(
        'import shutil\n'
        'def run(ctx):\n'
        '    ctx.progress(0.5, {"it": "metà", "en": "half"})\n'
        f'    target = ctx.output_dir / "out.gpkg"; shutil.copy(r"{model_output}", target)\n'
        '    return {"outputs": {"h3": target}, "metadata": {"city": ctx.city["name"]}}\n', encoding='utf-8')
    model = model_api.default_model(tmp_path / 'models')
    calls = []
    out = tmp_path / 'out'; out.mkdir()
    ctx = model_api.ModelContext(city=square_city.to_json(), boundary=tmp_path / 'b.gpkg', inputs={}, work_dir=tmp_path, output_dir=out,
                                 language='en', model_dir=model.folder, progress=lambda f, m=None: calls.append((f, m)))
    result = model.run(ctx)
    assert result['outputs']['h3'].name == 'out.gpkg' and result['metadata']['city'] == square_city.name
    assert calls == [(0.5, {'it': 'metà', 'en': 'half'})]
