import json
import sqlite3
import xml.etree.ElementTree as ET

import pyogrio
import pytest

from sonar_app import export
from sonar_app.export import docs, styles
from sonar_app.i18n import FILES, FOLDERS, LANGUAGES, STRINGS
from sonar_app.model_api import default_model


def test_every_text_exists_in_both_languages():
    for table in (STRINGS, FOLDERS, FILES):
        for key, entry in table.items():
            assert set(LANGUAGES) <= set(entry), key


def test_style_documents_are_well_formed():
    style = default_model().style('laeq')
    assert len(styles.class_ranges(style)) == len(style['colors'])
    for kind in ('polygon', 'line'):
        ET.fromstring(styles.qml(style, 'laeq_09_13', kind, 'Titolo', {'laeq_09_13': 'LAeq 09–13'}).split('\n', 1)[1])
        ET.fromstring(styles.sld(style, 'laeq_09_13', kind, 'feriale', 'Titolo'))
        document = json.loads(styles.lyrx(style, 'laeq_09_13', kind, 'Titolo', r'C:\x\a.gdb', 'h3_feriale', 'LAeq', 'Nessuna stima'))
        renderer = document['layerDefinitions'][0]['renderer']
        assert renderer['field'] == 'laeq_09_13' and len(renderer['breaks']) == len(style['colors'])


@pytest.mark.parametrize('language', LANGUAGES)
def test_delivery_folder(tmp_path, model_output, square_city, language):
    model = default_model()
    root = export.make_root(tmp_path, square_city.name)
    assert root.name.startswith('Sonar_Città_di_prova_')
    boundary = square_city.write_boundary(root / 'boundary.gpkg')
    written = export.export_results(model, {'h3': model_output}, root, square_city, boundary, language, lambda f, m: None, print)
    docs.write_documents(root, language, model, square_city)
    results = root / FOLDERS['results'][language]
    gpkg = results / FOLDERS['gpkg'][language] / written['gpkg'][0]
    layers = [name for name, _ in pyogrio.list_layers(gpkg) if name != 'layer_styles']
    assert layers == [l['export_name'][language] for l in model.output('h3')['layers']]
    with sqlite3.connect(gpkg) as con:
        assert {r[0] for r in con.execute('SELECT f_table_name FROM layer_styles WHERE useAsDefault')} == set(layers)
    gdb = next((results / FOLDERS['gdb'][language]).glob('*.gdb'))
    assert len(pyogrio.list_layers(gdb)) == 2 and len(written['lyrx']) == 2
    assert [p.name for p in (results / FOLDERS['maps'][language]).glob('*.png')] == written['png']
    assert len(written['png']) == 1 and written['png'][0].endswith('_Lden_Lnight.png')  # una tavola di sintesi per output
    with sqlite3.connect(gpkg) as con:
        assert con.execute('SELECT COUNT(*) FROM layer_styles').fetchone()[0] == 3 * len(layers)  # Lden, Lnight, LAeq
        default_qml = con.execute('SELECT styleQML FROM layer_styles WHERE useAsDefault LIMIT 1').fetchone()[0]
        names = {r[0] for r in con.execute('SELECT styleName FROM layer_styles')}
    assert all(len(n) <= 30 for n in names) and len(names) == 3
    assert 'attr="lden_ind"' in default_qml
    fields = pyogrio.read_info(gpkg, layer=layers[0])['fields']
    assert {'lden_ind', 'lnight_ind', 'laeq_09_13'} <= set(fields)
    for key in ('readme', 'license', 'authors'):
        text = (root / FILES[key][language]).read_text(encoding='utf-8-sig')
        assert text.strip()
    readme = (root / FILES['readme'][language]).read_text(encoding='utf-8-sig')
    assert model.manifest['documentation_url'] in readme and 'EuroGeographics' in readme
    assert 'Ivan Murano' in (root / FILES['authors'][language]).read_text(encoding='utf-8-sig')


def test_safe_names():
    assert export.safe_name('Reggio nell’Emilia: centro?') == 'Reggio_nell’Emilia_centro'
    assert export.gdb_name('h3_Città vecchia') == 'h3_Citta_vecchia'
    assert export.gdb_name('3d') == 'L_3d'


def test_delivery_without_indicators_keeps_band_maps(tmp_path, model_output, square_city):
    model = default_model()
    model.manifest = {k: v for k, v in model.manifest.items() if k != 'indicators'}
    root = export.make_root(tmp_path, square_city.name)
    boundary = square_city.write_boundary(root / 'boundary.gpkg')
    written = export.export_results(model, {'h3': model_output}, root, square_city, boundary, 'it', lambda f, m: None, print)
    assert len(written['png']) == 2 and 'indicators' not in written
