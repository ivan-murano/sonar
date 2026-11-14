"""Ricerca della città (geocoder Nominatim) e confine amministrativo europeo (Eurostat GISCO LAU).

Nominatim: una richiesta per ricerca, solo su conferma dell'utente (niente autocompletamento),
User-Agent identificabile, al massimo una richiesta al secondo, come chiede la policy OSMF.
Confini: servizio GISCO ID (LAU che contiene il punto, con geometria); se non risponde, file
LAU 1:1 milione dalla distribuzione GISCO, scaricato una volta e conservato in cache.
I confini GISCO/EuroGeographics sono utilizzabili per scopi non commerciali, con la dicitura
"© EuroGeographics for the administrative boundaries".
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import net
from .config import cache_dir

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
GISCO_ID_URL = 'https://gisco-services.ec.europa.eu/id/lau'
GISCO_LAU_FILES = 'https://gisco-services.ec.europa.eu/distribution/v2/lau/lau-{year}-files.json'
GISCO_LAU_BASE = 'https://gisco-services.ec.europa.eu/distribution/v2/lau/'
LAU_YEARS = (2024, 2023, 2021)
SETTLEMENT_TYPES = {'city', 'town', 'village', 'municipality', 'administrative', 'hamlet', 'suburb', 'borough', 'locality'}
BOUNDARY_ATTRIBUTION = '© EuroGeographics for the administrative boundaries; source: European Commission – Eurostat/GISCO'
BOUNDARY_LICENSE = 'Eurostat/GISCO: use permitted for non-commercial purposes with source acknowledgement (https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units)'
_lock = threading.Lock()
_last_call = [0.0]


@dataclass
class Candidate:
    name: str
    label: str
    lat: float
    lon: float
    country_code: str
    kind: str
    importance: float = 0.0


@dataclass
class City:
    """Città scelta: nome, paese, LAU e confine (GeoJSON in WGS84)."""
    name: str
    country_code: str
    lat: float
    lon: float
    lau_id: str
    gisco_id: str
    lau_name: str
    lau_year: int
    area_km2: float
    geometry: dict = field(repr=False)
    population: int | None = None
    source: str = 'gisco-id'

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> 'City':
        return cls(**data)

    def bbox(self):
        from shapely.geometry import shape
        return shape(self.geometry).bounds

    def write_boundary(self, path: Path):
        """Confine come GeoPackage (EPSG:4326) con gli attributi LAU."""
        import geopandas as gpd
        from shapely.geometry import shape
        frame = gpd.GeoDataFrame([{'name': self.name, 'lau_name': self.lau_name, 'lau_id': self.lau_id, 'gisco_id': self.gisco_id,
                                   'country': self.country_code, 'lau_year': self.lau_year, 'area_km2': round(self.area_km2, 3),
                                   'source': 'Eurostat GISCO LAU', 'attribution': BOUNDARY_ATTRIBUTION}],
                                 geometry=[shape(self.geometry)], crs=4326)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_file(path, driver='GPKG', engine='pyogrio')
        return path


def _respect_rate_limit():
    with _lock:
        wait = 1.05 - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


def search(query: str, language: str = 'it', limit: int = 10) -> list[Candidate]:
    """Luoghi abitati con questo nome, dal più importante; duplicati vicini uniti."""
    _respect_rate_limit()
    results = net.get_json(NOMINATIM_URL, params={'q': query, 'format': 'jsonv2', 'addressdetails': 1, 'limit': limit,
                                                  'featureType': 'settlement', 'accept-language': language})
    found = []
    for item in results:
        kind = item.get('addresstype') or item.get('type') or ''
        if item.get('category') not in ('place', 'boundary') and kind not in SETTLEMENT_TYPES:
            continue
        address = item.get('address') or {}
        name = item.get('name') or address.get('city') or address.get('town') or address.get('village') or query
        region = address.get('state') or address.get('region') or address.get('county') or ''
        country = address.get('country') or ''
        label = ', '.join(part for part in (name, region, country) if part)
        candidate = Candidate(name=name, label=label, lat=float(item['lat']), lon=float(item['lon']),
                              country_code=(address.get('country_code') or '').upper(), kind=kind, importance=float(item.get('importance') or 0))
        if any(abs(c.lat - candidate.lat) < 0.05 and abs(c.lon - candidate.lon) < 0.05 and c.name == candidate.name for c in found):
            continue
        found.append(candidate)
    return sorted(found, key=lambda c: -c.importance)


def _area_km2(geometry) -> float:
    import geopandas as gpd
    return float(gpd.GeoSeries([geometry], crs=4326).to_crs(3035).area.iloc[0] / 1e6)


def _from_feature(feature: dict, candidate: Candidate, year: int, source: str) -> City:
    from shapely.geometry import mapping, shape
    props = {k.upper(): v for k, v in (feature.get('properties') or {}).items()}
    geometry = shape(feature['geometry'])
    population = next((props[k] for k in sorted(props, reverse=True) if k.startswith('POP_') and not k.startswith('POP_DENS') and props[k]), None)
    return City(name=candidate.name, country_code=str(props.get('CNTR_CODE') or str(props.get('GISCO_ID') or '').partition('_')[0] or candidate.country_code), lat=candidate.lat, lon=candidate.lon,
                lau_id=str(props.get('LAU_ID') or props.get('LAU_CODE') or str(props.get('GISCO_ID') or '').partition('_')[2]),
                gisco_id=str(props.get('GISCO_ID') or props.get('ID') or feature.get('id') or ''),
                lau_name=str(props.get('LAU_NAME') or candidate.name), lau_year=year, area_km2=_area_km2(geometry),
                geometry=mapping(geometry), population=int(population) if population else None, source=source)


def boundary_from_service(candidate: Candidate, year: int) -> City | None:
    data = net.get_json(GISCO_ID_URL, params={'x': candidate.lon, 'y': candidate.lat, 'proj': 4326, 'year': year,
                                              'format': 'geojson', 'geometry': 'yes'})
    features = data.get('features') if isinstance(data, dict) else None
    if not features:
        return None
    return _from_feature(features[0], candidate, year, 'gisco-id')


def _find_lau_file(listing, year: int) -> str | None:
    """Cerca nel catalogo GISCO il file LAU 1:1M in EPSG:4326 (gpkg o geojson)."""
    paths = []

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            paths.append(value)
    walk(listing)
    for ext in ('.gpkg', '.geojson'):
        for path in paths:
            name = path.rsplit('/', 1)[-1]
            if name.startswith(f'LAU_RG_01M_{year}') and name.endswith(f'4326{ext}'):
                return path if path.startswith('http') else GISCO_LAU_BASE + path.lstrip('/')
    return None


def boundary_from_bulk(candidate: Candidate, year: int, progress=None) -> City | None:
    import pyogrio
    from shapely.geometry import Point, mapping
    target = cache_dir() / 'gisco'
    local = next(iter(sorted(target.glob(f'LAU_RG_01M_{year}_4326.*'))), None) if target.exists() else None
    if local is None or local.suffix == '.part':
        url = _find_lau_file(net.get_json(GISCO_LAU_FILES.format(year=year)), year)
        if not url:
            return None
        local = net.download(url, target / url.rsplit('/', 1)[-1], progress=progress)
    point = Point(candidate.lon, candidate.lat)
    frame = pyogrio.read_dataframe(local, bbox=(candidate.lon - 0.01, candidate.lat - 0.01, candidate.lon + 0.01, candidate.lat + 0.01))
    if frame.empty:
        return None
    frame = frame.to_crs(4326)
    hit = frame[frame.geometry.covers(point)]
    if hit.empty:
        return None
    row = hit.iloc[0]
    feature = {'properties': {k: (None if k == 'geometry' else row[k]) for k in hit.columns if k != 'geometry'}, 'geometry': mapping(row.geometry)}
    return _from_feature(feature, candidate, year, 'gisco-bulk')


def resolve_boundary(candidate: Candidate, progress=None) -> City | None:
    """Confine LAU che contiene il punto della città: anno più recente disponibile, servizio poi file."""
    errors = []
    for year in LAU_YEARS:
        try:
            city = boundary_from_service(candidate, year)
            if city:
                return city
        except Exception as exc:  # servizio non disponibile o formato cambiato: provo il file
            errors.append(f'service {year}: {exc}')
            try:
                city = boundary_from_bulk(candidate, year, progress)
                if city:
                    return city
            except Exception as bulk_exc:
                errors.append(f'bulk {year}: {bulk_exc}')
    if errors and len(errors) >= 2 * len(LAU_YEARS):
        raise ConnectionError('; '.join(errors))
    return None


def save_city(city: City, path: Path):
    path.write_text(json.dumps(city.to_json(), ensure_ascii=False), encoding='utf-8')


def load_city(path: Path) -> City:
    return City.from_json(json.loads(Path(path).read_text(encoding='utf-8')))
