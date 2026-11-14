"""Testi della consegna: LEGGIMI/README, LICENZA/LICENSE, AUTORI/AUTHORS."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import AUTHORS, __version__
from ..config import REPOSITORY_URL
from ..i18n import filename, folder, pick
from ..places import BOUNDARY_ATTRIBUTION

LICENSE_FILE = 'LICENSE.txt'


def software_license_text() -> str:
    """Testo della licenza del software (file LICENSE.txt del repository, bilingue)."""
    from ..config import bundle_dir, install_dir
    for base in (bundle_dir(), install_dir(), Path(__file__).resolve().parents[2]):
        path = base / LICENSE_FILE
        if path.exists():
            return path.read_text(encoding='utf-8')
    return 'Sonar — © Ivan Murano, Laura Ripoli. All rights reserved.'


README = {
    'it': """Sonar {version} — {city}
Generato il {when} con il modello «{model}» (versione {model_version}).

COSA C'È IN QUESTA CARTELLA
- {results}/{gpkg}: GeoPackage con lo stile già applicato (QGIS lo carica in automatico)
- {results}/{gdb}: File Geodatabase ESRI; in «{styles}» i file .lyrx per ArcGIS Pro
- {results}/{maps}: tavole PNG delle mappe
- {inputs}/{boundary}: confine amministrativo (Eurostat GISCO LAU {lau_year}, codice {lau_id})
- {inputs}/…: dati scaricati e usati dal modello, uno per sottocartella
- {sources_file}: provenienza, versione e licenza di ogni dato
- {license_file}: licenza del software e dei dati
- {authors_file}: autori del software e del modello
- {log_file}: registro dell'elaborazione

COME LEGGERE I RISULTATI
{notes}

Spiegazione del modello: {doc_url}
Software Sonar: {repo_url}

ATTRIBUZIONI
© OpenStreetMap contributors (ODbL 1.0) · © Overture Maps Foundation · ESA WorldCover 2021 (CC BY 4.0)
{boundary_attribution}
""",
    'en': """Sonar {version} — {city}
Generated on {when} with the model “{model}” (version {model_version}).

WHAT IS IN THIS FOLDER
- {results}/{gpkg}: GeoPackage with the style already applied (QGIS loads it automatically)
- {results}/{gdb}: ESRI File Geodatabase; “{styles}” holds .lyrx files for ArcGIS Pro
- {results}/{maps}: PNG map sheets
- {inputs}/{boundary}: administrative boundary (Eurostat GISCO LAU {lau_year}, code {lau_id})
- {inputs}/…: data downloaded and used by the model, one per subfolder
- {sources_file}: origin, version and license of every dataset
- {license_file}: software and data license
- {authors_file}: authors of the software and of the model
- {log_file}: processing log

HOW TO READ THE RESULTS
{notes}

Model explanation: {doc_url}
Sonar software: {repo_url}

ATTRIBUTIONS
© OpenStreetMap contributors (ODbL 1.0) · © Overture Maps Foundation · ESA WorldCover 2021 (CC BY 4.0)
{boundary_attribution}
""",
}

DATA_LICENSES = {
    'it': """
LICENZE DEI DATI E DEI RISULTATI
{output_license}
- OpenStreetMap: ODbL 1.0, https://www.openstreetmap.org/copyright — i risultati sono opere derivate (share-alike).
- Overture Maps Places: CDLA Permissive 2.0 e licenze dei fornitori, https://docs.overturemaps.org/attribution/
- ESA WorldCover 2021: CC BY 4.0, https://esa-worldcover.org/en/data-access
- Confini Eurostat GISCO LAU: uso non commerciale con citazione della fonte,
  https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units — {boundary_attribution}
""",
    'en': """
DATA AND RESULTS LICENSES
{output_license}
- OpenStreetMap: ODbL 1.0, https://www.openstreetmap.org/copyright — results are derivative works (share-alike).
- Overture Maps Places: CDLA Permissive 2.0 and provider licenses, https://docs.overturemaps.org/attribution/
- ESA WorldCover 2021: CC BY 4.0, https://esa-worldcover.org/en/data-access
- Eurostat GISCO LAU boundaries: non-commercial use with source acknowledgement,
  https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units — {boundary_attribution}
""",
}

AUTHORS_TEXT = {
    'it': """Sonar {version}
Software: {software_authors}
Modello «{model}» {model_version}: {model_authors}
Spiegazione del modello: {doc_url}
Repository: {repo_url}
""",
    'en': """Sonar {version}
Software: {software_authors}
Model “{model}” {model_version}: {model_authors}
Model explanation: {doc_url}
Repository: {repo_url}
""",
}


def write_documents(root: Path, language: str, model, city, notes_extra: str = '') -> list[Path]:
    manifest = model.manifest
    values = dict(version=__version__, city=city.name, when=datetime.now().strftime('%d/%m/%Y %H:%M' if language == 'it' else '%Y-%m-%d %H:%M'),
                  model=pick(manifest['name'], language), model_version=model.version, results=folder('results', language),
                  gpkg=folder('gpkg', language), gdb=folder('gdb', language), styles=folder('arcgis_styles', language), maps=folder('maps', language),
                  inputs=folder('inputs', language), boundary=folder('boundary', language), lau_year=city.lau_year, lau_id=city.gisco_id or city.lau_id,
                  sources_file=filename('sources', language), license_file=filename('license', language), authors_file=filename('authors', language),
                  log_file=filename('log', language), notes=(pick(manifest.get('notes'), language) + notes_extra).strip(),
                  doc_url=manifest.get('documentation_url', REPOSITORY_URL), repo_url=REPOSITORY_URL, boundary_attribution=BOUNDARY_ATTRIBUTION,
                  software_authors=', '.join(AUTHORS), model_authors=', '.join(manifest.get('authors', [])),
                  output_license=pick(manifest.get('output_license'), language))
    paths = []
    for key, text in (('readme', README[language].format(**values)),
                      ('license', software_license_text() + DATA_LICENSES[language].format(**values)),
                      ('authors', AUTHORS_TEXT[language].format(**values))):
        path = root / filename(key, language)
        path.write_text(text.replace('\n', '\r\n'), encoding='utf-8-sig')  # Blocco note di Windows
        paths.append(path)
    return paths
