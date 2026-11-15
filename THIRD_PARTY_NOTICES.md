# Componenti di terze parti / Third-party components

Sonar include i componenti seguenti, ciascuno con la propria licenza. L'installazione Windows contiene i testi completi nella cartella `licenses/`, raccolti dai pacchetti installati al momento della build (`build/collect_licenses.py`).

| Componente | Licenza | Note |
|---|---|---|
| Python | PSF License 2.0 | interprete incluso dall'eseguibile |
| Qt 6 / PySide6 | LGPL v3 | librerie installate come file separati e sostituibili; sorgenti: https://code.qt.io, https://download.qt.io/official_releases/QtForPython/ |
| GDAL (in pyogrio e rasterio) | MIT/X | lettura e scrittura GeoPackage, File Geodatabase, GeoTIFF |
| PROJ (in pyproj, pyogrio, rasterio) | MIT | |
| GEOS (in shapely) | LGPL v2.1 | libreria dinamica separata |
| NumPy, pandas, SciPy, scikit-learn, joblib, geopandas, shapely, rasterio | BSD 3-Clause | |
| pyogrio, pyproj, urllib3, holidays, overturemaps, Pillow (MIT-CMU) | MIT | |
| pyarrow, h3, requests | Apache 2.0 | |
| pyosmium | BSD 2-Clause; libosmium Boost Software License 1.0 | |
| matplotlib | Matplotlib License (PSF-based) | |
| numba, llvmlite | BSD 2-Clause; LLVM: Apache 2.0 con eccezione LLVM | compilazione dei calcoli geometrici |
| Quicksand (font) | SIL Open Font License 1.1 | `sonar_app/assets/fonts/OFL.txt` |
| PyInstaller (bootloader) | GPL v2 con eccezione per i programmi creati | consente la distribuzione dell'eseguibile |
| Inno Setup (programma di installazione) | Inno Setup License | |

Dati scaricati durante l'uso (non inclusi nel software): OpenStreetMap (ODbL 1.0), Overture Maps (CDLA Permissive 2.0 e licenze dei fornitori), ESA WorldCover 2021 (CC BY 4.0), confini Eurostat GISCO (© EuroGeographics, uso non commerciale), geocoder Nominatim (policy OSMF).
