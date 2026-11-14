"""Stili per classi dichiarati dal modello: QML (QGIS), SLD (OGC) e layer file .lyrx (ArcGIS Pro)."""
from __future__ import annotations

import json
import uuid
from xml.sax.saxutils import escape

QGIS_VERSION = '3.34.0'


def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip('#')
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def class_ranges(style: dict, low=-1000.0, high=1000.0):
    """(min, max, colore, etichetta) per ogni classe: < primo limite, intervalli, ≥ ultimo limite."""
    breaks, colors = style['breaks'], style['colors']
    edges = [low, *breaks, high]
    ranges = []
    for i, color in enumerate(colors):
        lo, hi = edges[i], edges[i + 1]
        if i == 0:
            label = f'< {breaks[0]:g}'
        elif i == len(colors) - 1:
            label = f'≥ {breaks[-1]:g}'
        else:
            label = f'{lo:g} – {hi:g}'
        ranges.append((lo, hi, color, label))
    return ranges


def _qml_symbol(index: int, color: str, geometry: str) -> str:
    r, g, b = rgb(color)
    if geometry == 'line':
        return (f'<symbol type="line" name="{index}" alpha="1" clip_to_extent="1" force_rhr="0">'
                f'<layer class="SimpleLine" enabled="1" locked="0" pass="0"><Option type="Map">'
                f'<Option name="line_color" type="QString" value="{r},{g},{b},255"/>'
                f'<Option name="line_style" type="QString" value="solid"/>'
                f'<Option name="line_width" type="QString" value="0.5"/>'
                f'<Option name="line_width_unit" type="QString" value="MM"/>'
                f'<Option name="capstyle" type="QString" value="round"/>'
                f'<Option name="joinstyle" type="QString" value="round"/>'
                f'</Option></layer></symbol>')
    return (f'<symbol type="fill" name="{index}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleFill" enabled="1" locked="0" pass="0"><Option type="Map">'
            f'<Option name="color" type="QString" value="{r},{g},{b},255"/>'
            f'<Option name="style" type="QString" value="solid"/>'
            f'<Option name="outline_style" type="QString" value="no"/>'
            f'<Option name="outline_color" type="QString" value="{r},{g},{b},255"/>'
            f'<Option name="outline_width" type="QString" value="0"/>'
            f'</Option></layer></symbol>')


def qml(style: dict, field: str, geometry: str, title: str, aliases: dict | None = None) -> str:
    """Renderer graduato di QGIS sul campo indicato; geometry 'polygon' o 'line'."""
    ranges = class_ranges(style)
    range_xml = ''.join(f'<range lower="{lo:g}" upper="{hi:g}" symbol="{i}" label="{escape(label)}" render="true" uuid="{{{uuid.uuid4()}}}"/>'
                        for i, (lo, hi, _, label) in enumerate(ranges))
    symbols = ''.join(_qml_symbol(i, color, geometry) for i, (_, _, color, _) in enumerate(ranges))
    alias_xml = ''.join(f'<alias field="{escape(name)}" index="{i}" name="{escape(text)}"/>' for i, (name, text) in enumerate((aliases or {}).items()))
    return (f"<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
            f'<qgis version="{QGIS_VERSION}" styleCategories="Symbology|Fields|Legend">'
            f'<renderer-v2 type="graduatedSymbol" attr="{escape(field)}" graduatedMethod="GraduatedColor" symbollevels="0" forceraster="0" enableorderby="0" referencescale="-1">'
            f'<ranges>{range_xml}</ranges><symbols>{symbols}</symbols>'
            f'<source-symbol>{_qml_symbol(0, style["colors"][0], geometry)}</source-symbol>'
            f'<classificationMethod id="Fixed"><symmetricMode enabled="0" symmetrypoint="0" astride="0"/><labelFormat format="%1 - %2" trimtrailingzeroes="1" labelprecision="0"/>'
            f'<parameters><Option/></parameters><extraInformation/></classificationMethod>'
            f'<rotation/><sizescale/></renderer-v2>'
            f'<aliases>{alias_xml}</aliases>'
            f'<layerGeometryType>{1 if geometry == "line" else 2}</layerGeometryType></qgis>')


def sld(style: dict, field: str, geometry: str, layer_name: str, title: str) -> str:
    rules = []
    for lo, hi, color, label in class_ranges(style):
        lower = '' if lo <= -1000 else (f'<ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>{field}</ogc:PropertyName>'
                                         f'<ogc:Literal>{lo:g}</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo>')
        upper = '' if hi >= 1000 else (f'<ogc:PropertyIsLessThan><ogc:PropertyName>{field}</ogc:PropertyName>'
                                        f'<ogc:Literal>{hi:g}</ogc:Literal></ogc:PropertyIsLessThan>')
        condition = f'<ogc:And>{lower}{upper}</ogc:And>' if lower and upper else (lower or upper)
        symbolizer = (f'<se:LineSymbolizer><se:Stroke><se:SvgParameter name="stroke">{color}</se:SvgParameter>'
                      f'<se:SvgParameter name="stroke-width">1.5</se:SvgParameter></se:Stroke></se:LineSymbolizer>' if geometry == 'line' else
                      f'<se:PolygonSymbolizer><se:Fill><se:SvgParameter name="fill">{color}</se:SvgParameter></se:Fill></se:PolygonSymbolizer>')
        rules.append(f'<se:Rule><se:Name>{escape(label)}</se:Name><se:Description><se:Title>{escape(label)}</se:Title></se:Description>'
                     f'<ogc:Filter>{condition}</ogc:Filter>{symbolizer}</se:Rule>')
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:se="http://www.opengis.net/se" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1.0" '
            'xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd">'
            f'<NamedLayer><se:Name>{escape(layer_name)}</se:Name><UserStyle><se:Name>{escape(title)}</se:Name>'
            f'<se:FeatureTypeStyle>{"".join(rules)}</se:FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>')


def _cim_color(hex_color: str, alpha=100):
    r, g, b = rgb(hex_color)
    return {'type': 'CIMRGBColor', 'values': [r, g, b, alpha]}


def _cim_symbol(color: str, geometry: str):
    if geometry == 'line':
        symbol = {'type': 'CIMLineSymbol', 'symbolLayers': [
            {'type': 'CIMSolidStroke', 'enable': True, 'capStyle': 'Round', 'joinStyle': 'Round', 'lineStyle3D': 'Strip',
             'miterLimit': 10, 'width': 1.2, 'color': _cim_color(color)}]}
    else:
        symbol = {'type': 'CIMPolygonSymbol', 'symbolLayers': [
            {'type': 'CIMSolidStroke', 'enable': False, 'capStyle': 'Round', 'joinStyle': 'Round', 'lineStyle3D': 'Strip',
             'miterLimit': 10, 'width': 0, 'color': _cim_color('#000000', 0)},
            {'type': 'CIMSolidFill', 'enable': True, 'color': _cim_color(color)}]}
    return {'type': 'CIMSymbolReference', 'symbol': symbol}


def lyrx(style: dict, field: str, geometry: str, layer_title: str, gdb_path: str, feature_class: str, heading: str, no_data_label: str) -> str:
    """Layer file ArcGIS Pro (CIM) con renderer a classi sul feature class del File Geodatabase."""
    uri = f'CIMPATH=sonar/{feature_class.lower()}.json'
    breaks = [{'type': 'CIMClassBreak', 'label': label, 'patch': 'Default', 'symbol': _cim_symbol(color, geometry),
               'upperBound': (hi if hi < 1000 else 1000)} for lo, hi, color, label in class_ranges(style)]
    layer = {
        'type': 'CIMFeatureLayer', 'name': layer_title, 'uRI': uri, 'useSourceMetadata': True, 'expanded': True,
        'layerType': 'Operational', 'showLegends': True, 'visibility': True, 'displayCacheType': 'Permanent', 'maxDisplayCacheAge': 5,
        'showPopups': True, 'serviceLayerID': -1, 'refreshRate': -1, 'refreshRateUnit': 'esriTimeUnitsSeconds', 'blendingMode': 'Alpha',
        'autoGenerateFeatureTemplates': True, 'featureElevationExpression': '0', 'htmlPopupEnabled': True, 'selectable': True,
        'featureCacheType': 'Session', 'scaleSymbols': True, 'snappable': True,
        'featureTable': {'type': 'CIMFeatureTable', 'displayField': 'unit_id', 'editable': True,
                         'dataConnection': {'type': 'CIMStandardDataConnection', 'workspaceConnectionString': f'DATABASE={gdb_path}',
                                            'workspaceFactory': 'FileGDB', 'dataset': feature_class, 'datasetType': 'esriDTFeatureClass'},
                         'studyAreaSpatialRel': 'esriSpatialRelUndefined', 'searchOrder': 'esriSearchOrderSpatial'},
        'renderer': {'type': 'CIMClassBreaksRenderer', 'barrierWeight': 'High', 'breaks': breaks, 'classBreakType': 'GraduatedColor',
                     'classificationMethod': 'Manual', 'field': field, 'minimumBreak': -1000, 'showInAscendingOrder': True,
                     'heading': heading, 'sampleSize': 10000, 'useDefaultSymbol': True, 'defaultLabel': no_data_label,
                     'defaultSymbol': _cim_symbol(style.get('no_data_color', '#d5d9dc'), geometry), 'defaultSymbolPatch': 'Default',
                     'polygonSymbolColorTarget': 'Fill', 'normalizationType': 'Nothing', 'exclusionLabel': '<excluded>',
                     'useExclusionSymbol': False, 'exclusionSymbolPatch': 'Default'},
    }
    document = {'type': 'CIMLayerDocument', 'version': '3.1.0', 'build': 41833, 'layers': [uri], 'layerDefinitions': [layer]}
    return json.dumps(document, ensure_ascii=False, indent=2)
