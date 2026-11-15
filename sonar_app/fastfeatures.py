"""Feature statiche del modello Pharos Noise calcolate più in fretta, con gli stessi risultati.

Il modello (`src/prediction_features.py`, `src/sonar/prepare.py`) calcola per ogni ricevitore lunghezza delle
strade, copertura degli edifici e conteggi dei POI entro 100/250/500 m, con buffer poligonali di 64 lati e
un'intersezione GEOS per ogni coppia ricevitore-geometria, su 2-3 thread. Nelle città grandi è la fase più lunga.

Qui le stesse definizioni sono calcolate così (risultati identici entro ~1e-8, verificati a ogni esecuzione dal
modello stesso contro la sua implementazione di riferimento):
1) una sola interrogazione dell'indice spaziale per strato e somme cumulative per raggio;
2) geometrie con bbox dentro il cerchio inscritto del 64-gono: misura intera senza test geometrici;
3) geometrie a cavallo del bordo: ritaglio vettoriale (numpy) con i soli lati del 64-gono dello spicchio che le
   contiene (Cyrus-Beck per i segmenti stradali, Sutherland-Hodgman per gli anelli degli edifici), in coordinate
   relative al ricevitore;
4) blocchi di ricevitori distribuiti su più processi.

L'adattatore del modello sostituisce `sonar.prepare.compute_static_features` con `compute_static_features` di questo
modulo; il codice del modello non viene modificato.
"""
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

GROUPS = ['nightlife','food','education','retail','health','leisure','transport','business','other']
KMAX = 10          # lati per spicchio oltre i quali si ritaglia con tutti i lati
BLOCK = 400_000    # coppie per blocco vettoriale (memoria)


def _bbox_dist(b, xy):
    dx = np.maximum(np.maximum(b[:, 0] - xy[:, 0], 0), xy[:, 0] - b[:, 2])
    dy = np.maximum(np.maximum(b[:, 1] - xy[:, 1], 0), xy[:, 1] - b[:, 3])
    fx = np.maximum(np.abs(b[:, 0] - xy[:, 0]), np.abs(b[:, 2] - xy[:, 0]))
    fy = np.maximum(np.abs(b[:, 1] - xy[:, 1]), np.abs(b[:, 3] - xy[:, 1]))
    return np.hypot(dx, dy), np.hypot(fx, fy)


def _ragged(starts, counts):
    """Indici concatenati di intervalli [start, start+count)."""
    total = counts.sum()
    owner = np.repeat(np.arange(len(counts)), counts)
    offs = np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
    return owner, np.repeat(starts, counts) + offs


class _Lines:
    """Segmenti delle strade in forma piatta."""
    def __init__(self, geoms):
        coords, gid = shapely.get_coordinates(geoms, return_index=True)
        # segmenti tra vertici consecutivi della stessa geometria (multi-linee: parti separate)
        parts, pidx = shapely.get_parts(geoms, return_index=True)
        pc, pid = shapely.get_coordinates(parts, return_index=True)
        same = pid[1:] == pid[:-1]
        self.s = pc[:-1][same]; self.e = pc[1:][same]; seg_geom = pidx[pid[:-1][same]]
        order = np.argsort(seg_geom, kind='stable'); self.s, self.e, seg_geom = self.s[order], self.e[order], seg_geom[order]
        self.count = np.bincount(seg_geom, minlength=len(geoms)); self.start = np.cumsum(self.count) - self.count
        self.sx, self.sy = np.ascontiguousarray(self.s[:, 0]), np.ascontiguousarray(self.s[:, 1])
        self.ex, self.ey = np.ascontiguousarray(self.e[:, 0]), np.ascontiguousarray(self.e[:, 1])

    def clip_length(self, g, A, D, valid):
        """Lunghezza dentro l'intersezione dei semipiani (A punto, D direzione; interno a sinistra) per ogni coppia."""
        pair, seg = _ragged(self.start[g], self.count[g])
        s, e = self.s[seg], self.e[seg]
        a, d, v = A[pair], D[pair], valid[pair]
        fs = d[..., 0] * (s[:, None, 1] - a[..., 1]) - d[..., 1] * (s[:, None, 0] - a[..., 0])
        fe = d[..., 0] * (e[:, None, 1] - a[..., 1]) - d[..., 1] * (e[:, None, 0] - a[..., 0])
        fs = np.where(v, fs, 1.0); fe = np.where(v, fe, 1.0)
        with np.errstate(divide='ignore', invalid='ignore'):
            t = fs / (fs - fe)
        t0 = np.where((fs < 0) & (fe >= 0), t, 0.0).max(1)
        t1 = np.where((fs >= 0) & (fe < 0), t, 1.0).min(1)
        dead = ((fs < 0) & (fe < 0)).any(1)
        frac = np.where(dead, 0.0, np.clip(t1 - t0, 0.0, 1.0))
        seg_len = np.hypot(*(e - s).T)
        return np.bincount(pair, weights=frac * seg_len, minlength=len(g))


class _Rings:
    """Anelli degli edifici in forma piatta (senza vertice di chiusura), con segno +1 esterno / -1 foro."""
    def __init__(self, geoms):
        parts, pidx = shapely.get_parts(geoms, return_index=True)
        rings, ridx = shapely.get_rings(parts, return_index=True)
        first = np.r_[True, ridx[1:] != ridx[:-1]]
        sign = np.where(first, 1.0, -1.0)
        coords, cid = shapely.get_coordinates(rings, return_index=True)
        n = np.bincount(cid, minlength=len(rings))
        keep = np.ones(len(coords), bool); keep[np.cumsum(n) - 1] = False   # toglie il vertice di chiusura
        self.xy = coords[keep]; self.n = n - 1; self.start = np.cumsum(self.n) - self.n
        self.sign = sign; rgeom = pidx[ridx]
        order = np.argsort(rgeom, kind='stable')
        self.ring_order = order
        self.rcount = np.bincount(rgeom, minlength=len(geoms)); self.rstart = np.cumsum(self.rcount) - self.rcount
        self.ring_area = shapely.area(shapely.polygons(rings))
        self.vx, self.vy = np.ascontiguousarray(self.xy[:, 0]), np.ascontiguousarray(self.xy[:, 1])
        self.n = self.n.astype(np.int64); self.start = self.start.astype(np.int64)

    def clip_area(self, g, A, D, valid, center):
        """Area di ogni geometria dentro l'intersezione dei semipiani. Anelli interamente dentro: area intera;
        interamente fuori da un semipiano: zero; solo gli anelli a cavallo passano dal ritaglio Sutherland-Hodgman."""
        pair, rpos = _ragged(self.rstart[g], self.rcount[g])
        ring = self.ring_order[rpos]
        n_r = self.n[ring]
        rid, vidx = _ragged(self.start[ring], n_r)
        pts = self.xy[vidx] - center[pair][rid]   # coordinate relative: niente cancellazione numerica
        A = A - center[:, None, :]
        ar, dr, vr = A[pair], D[pair], valid[pair]                  # semipiani per anello
        a, d = ar[rid], dr[rid]
        f = d[..., 0] * (pts[:, None, 1] - a[..., 1]) - d[..., 1] * (pts[:, None, 0] - a[..., 0])
        inside = (f >= 0) | ~vr[rid]
        starts = np.cumsum(n_r) - n_r
        all_in = np.logical_and.reduceat(inside.all(1), starts)
        all_out = np.logical_and.reduceat(~inside, starts, axis=0).any(1)
        area = np.where(all_in, self.ring_area[ring], 0.0)
        crossing = np.flatnonzero(~all_in & ~all_out)
        if crossing.size:
            sub_rid, sub_v = _ragged(starts[crossing], n_r[crossing])
            area[crossing] = _sutherland_hodgman(pts[sub_v], sub_rid, n_r[crossing], ar[crossing], dr[crossing], vr[crossing])
        return np.bincount(pair, weights=area * self.sign[ring], minlength=len(g))


def _sutherland_hodgman(pts, rid, n_r, a_r, d_r, v_r):
    """Area (valore assoluto) degli anelli ritagliati in sequenza dai semipiani (a_r, d_r, v_r per anello)."""
    n_rings = len(n_r)
    for j in range(a_r.shape[1]):
        if len(pts) == 0:
            break
        active = v_r[:, j]
        if not active.any():
            continue
        a, d = a_r[rid, j], d_r[rid, j]
        fj = d[:, 0] * (pts[:, 1] - a[:, 1]) - d[:, 1] * (pts[:, 0] - a[:, 0])
        fj = np.where(active[rid], fj, 1.0)
        if (fj >= 0).all():
            continue
        start = np.cumsum(n_r) - n_r
        idx = np.arange(len(pts))
        prev = idx - 1
        first = start[rid]
        is_first = idx == first
        prev[is_first] = (first + n_r[rid] - 1)[is_first]
        fe, fs = fj, fj[prev]
        ine, ins = fe >= 0, fs >= 0
        need_i = ine != ins
        cnt = ine.astype(np.int64) + need_i
        out_owner = np.repeat(idx, cnt)
        pos_in = np.arange(out_owner.size) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        use_inter = need_i[out_owner] & (pos_in == 0)
        new = pts[out_owner]
        k = np.flatnonzero(use_inter)
        if k.size:
            o = out_owner[k]
            t = fs[o] / (fs[o] - fe[o])
            sp = pts[prev[o]]
            new[k] = sp + t[:, None] * (pts[o] - sp)
        rid = rid[out_owner]
        n_r = np.bincount(rid, minlength=n_rings)
        pts = new
    if len(pts) == 0:
        return np.zeros(n_rings)
    start = np.cumsum(n_r) - n_r
    idx = np.arange(len(pts))
    nxt = idx + 1
    last = start[rid] + n_r[rid] - 1
    is_last = idx == last
    nxt[is_last] = start[rid][is_last]
    cross = pts[:, 0] * pts[nxt, 1] - pts[nxt, 0] * pts[:, 1]
    return np.abs(np.bincount(rid, weights=cross, minlength=n_rings)) / 2


class FastSpatialFeatureContext:
    def __init__(self, roads, buildings, osm, places):
        self.roads = roads.geometry.to_numpy(); self.roadtree = shapely.STRtree(self.roads); self.lengths = shapely.length(self.roads)
        self.buildings = buildings.geometry.to_numpy(); self.buildtree = shapely.STRtree(self.buildings); self.areas = shapely.area(self.buildings)
        self.road_bounds = shapely.bounds(self.roads); self.build_bounds = shapely.bounds(self.buildings)
        self.lines = _Lines(self.roads); self.rings = _Rings(self.buildings)
        from . import fastkernels
        self.kernels = fastkernels if fastkernels.available() and os.environ.get('SONAR_NUMBA', '1') != '0' else None
        motor = ['motorway','trunk','primary','secondary','tertiary','residential','unclassified','living_street','service']
        roadkind = roads.highway.str.replace('_link','',regex=False)
        self.major = roadkind.isin(motor[:5]).to_numpy(); self.motor = roadkind.isin(motor).to_numpy()
        self.pois = {name:(frame, shapely.STRtree(frame.geometry.to_numpy())) for name, frame in [('osm',osm),('ovt',places)]}
        code = {g: i for i, g in enumerate(GROUPS)}
        self._poi_xy = {k: shapely.get_coordinates(f.geometry.to_numpy()) for k, (f, _) in self.pois.items()}
        self._poi_group = {k: f.group.map(code).fillna(len(GROUPS)).astype(np.int64).to_numpy() for k, (f, _) in self.pois.items()}
        self._poi_hours = {'osm': osm.opening_hours.notna().to_numpy()}

    @staticmethod
    def _planes(ring, xy, b, p):
        """Semipiani dei lati del 64-gono che coprono lo spicchio della bbox; full=True se serve GEOS."""
        nv = ring.shape[1]
        rel0 = ring[0] - xy[0]
        ang = np.arctan2(rel0[:, 1], rel0[:, 0]); order = np.argsort(ang); ang = ang[order]
        px, py = xy[p, 0], xy[p, 1]
        cxs = np.stack([b[:, 0], b[:, 2], b[:, 2], b[:, 0]], 1) - px[:, None]
        cys = np.stack([b[:, 1], b[:, 1], b[:, 3], b[:, 3]], 1) - py[:, None]
        phi0 = np.arctan2(cys.mean(1), cxs.mean(1))
        d = np.angle(np.exp(1j * (np.arctan2(cys, cxs) - phi0[:, None])))
        full = (px >= b[:, 0]) & (px <= b[:, 2]) & (py >= b[:, 1]) & (py <= b[:, 3])
        ta = np.angle(np.exp(1j * (phi0 + d.min(1)))); tb = np.angle(np.exp(1j * (phi0 + d.max(1))))
        ka = np.searchsorted(ang, ta - 1e-9, side='right') - 1
        kb = np.searchsorted(ang, tb + 1e-9, side='left')
        k = np.mod(kb - ka, nv)                      # numero di lati
        k = np.where(k == 0, 1, k)
        full |= (k > KMAX) | ((d.max(1) - d.min(1)) > np.pi * 0.9)
        j = np.arange(KMAX)
        valid = (j[None, :] < k[:, None]) & ~full[:, None]
        i0 = np.mod(ka[:, None] + j[None, :], nv); i1 = np.mod(i0 + 1, nv)
        v0 = ring[p[:, None], order[i0]]; v1 = ring[p[:, None], order[i1]]
        return v0, v1 - v0, valid, full

    def _road_lengths(self, xy, ring, radius, pairs, inscribed):
        """Lunghezza di ogni strada dentro il 64-gono, segmento per segmento."""
        p, g = pairs
        _, dmax = _bbox_dist(self.road_bounds[g], xy[p])
        out = self.lengths[g].astype(float).copy()
        rest = np.flatnonzero(dmax >= radius * inscribed - 1e-6)
        if rest.size == 0:
            return out
        nv = ring.shape[1]
        rel = ring[0] - xy[0]; ang0 = np.arctan2(rel[:, 1], rel[:, 0]); order = np.argsort(ang0); ang = ang0[order]
        rin, rout = radius * inscribed - 1e-6, radius + 1e-6
        acc = np.zeros(rest.size)
        for lo in range(0, rest.size, BLOCK // 8):
            r = rest[lo:lo + BLOCK // 8]
            pair, seg = _ragged(self.lines.start[g[r]], self.lines.count[g[r]])
            c = xy[p[r]][pair]
            s0 = self.lines.s[seg] - c; e0 = self.lines.e[seg] - c          # coordinate relative al ricevitore
            de = e0 - s0; L2 = (de ** 2).sum(1)
            with np.errstate(divide='ignore', invalid='ignore'):
                tf = np.clip(-(s0 * de).sum(1) / L2, 0, 1)
            tf = np.where(L2 > 0, tf, 0.0)
            foot = s0 + tf[:, None] * de
            # due semisegmenti: s0->foot e foot->e0 (distanza dal centro monotona su ciascuno)
            a = np.concatenate([s0, foot]); b = np.concatenate([foot, e0]); own = np.concatenate([pair, pair])
            ra, rb = np.hypot(*a.T), np.hypot(*b.T)
            seg_len = np.hypot(*(b - a).T)
            keep = seg_len > 0
            inside = keep & (np.maximum(ra, rb) <= rin)
            near = keep & ~inside & (np.minimum(ra, rb) < rout)
            contrib = np.where(inside, seg_len, 0.0)
            idx = np.flatnonzero(near)
            if idx.size:
                aa, bb = a[idx], b[idx]
                ta = np.arctan2(aa[:, 1], aa[:, 0]); tb = np.arctan2(bb[:, 1], bb[:, 0])
                # estremo nel centro: si usa la direzione dell'altro estremo
                za, zb = np.hypot(*aa.T) < 1e-9, np.hypot(*bb.T) < 1e-9
                ta = np.where(za, tb, ta); tb = np.where(zb, ta, tb)
                dlt = np.angle(np.exp(1j * (tb - ta)))
                lo_a = np.where(dlt >= 0, ta, ta + dlt); hi_a = lo_a + np.abs(dlt)
                ka = np.searchsorted(ang, np.angle(np.exp(1j * lo_a)) - 1e-9, side='right') - 1
                kb = np.searchsorted(ang, np.angle(np.exp(1j * hi_a)) + 1e-9, side='left')
                k = np.maximum(np.mod(kb - ka, nv), 1)
                frac = np.zeros(idx.size)
                for kk in np.unique(k):
                    sel = np.flatnonzero(k == kk)
                    j = np.arange(kk)
                    i0 = np.mod(ka[sel, None] + j[None, :], nv); i1 = np.mod(i0 + 1, nv)
                    pp = p[r][own[idx[sel]]]
                    v0 = ring[pp[:, None], order[i0]] - xy[pp][:, None, :]; v1 = ring[pp[:, None], order[i1]] - xy[pp][:, None, :]
                    d = v1 - v0
                    sa, sb = aa[sel], bb[sel]
                    fs = d[..., 0] * (sa[:, None, 1] - v0[..., 1]) - d[..., 1] * (sa[:, None, 0] - v0[..., 0])
                    fe = d[..., 0] * (sb[:, None, 1] - v0[..., 1]) - d[..., 1] * (sb[:, None, 0] - v0[..., 0])
                    with np.errstate(divide='ignore', invalid='ignore'):
                        t = fs / (fs - fe)
                    t0 = np.where((fs < 0) & (fe >= 0), t, 0.0).max(1)
                    t1 = np.where((fs >= 0) & (fe < 0), t, 1.0).min(1)
                    dead = ((fs < 0) & (fe < 0)).any(1)
                    frac[sel] = np.where(dead, 0.0, np.clip(t1 - t0, 0.0, 1.0))
                contrib[idx] = frac * seg_len[idx]
            acc[lo:lo + r.size] = np.bincount(own, weights=contrib, minlength=r.size)
        out[rest] = acc
        return out

    def _measure(self, kind, xy, buffers, ring, radius, pairs, inscribed, all_rest=False):
        if self.kernels is not None and len(pairs[0]):
            out = self._measure_compiled(kind, xy, ring, radius, pairs, inscribed)
            bad = np.flatnonzero(~np.isfinite(out))
            if bad.size == 0:
                return out
            out[bad] = self._measure_numpy(kind, xy, buffers, ring, radius, pairs[:, bad], inscribed)
            return out
        return self._measure_numpy(kind, xy, buffers, ring, radius, pairs, inscribed)

    def _measure_compiled(self, kind, xy, ring, radius, pairs, inscribed):
        k = self.kernels
        p = np.ascontiguousarray(pairs[0], dtype=np.int64); g = np.ascontiguousarray(pairs[1], dtype=np.int64)
        cx, cy = np.ascontiguousarray(xy[:, 0]), np.ascontiguousarray(xy[:, 1])
        out = np.empty(len(p))
        r_in2 = (radius * inscribed - 1e-6) ** 2
        if kind == 'road':
            L = self.lines
            k.road_lengths(p, g, cx, cy, ring, r_in2, radius + 1e-6, L.start, L.count, L.sx, L.sy, L.ex, L.ey, out)
        else:
            R = self.rings
            k.ring_areas(p, g, cx, cy, ring, r_in2, R.rstart, R.rcount, R.ring_order, R.start, R.n, R.vx, R.vy, R.sign, R.ring_area, out)
        return out

    def _measure_numpy(self, kind, xy, buffers, ring, radius, pairs, inscribed):
        if kind == 'road':
            return self._road_lengths(xy, ring, radius, pairs, inscribed)
        bounds, values = (self.road_bounds, self.lengths) if kind == 'road' else (self.build_bounds, self.areas)
        clip = self.lines.clip_length if kind == 'road' else self.rings.clip_area
        p, g = pairs
        _, dmax = _bbox_dist(bounds[g], xy[p])
        out = values[g].astype(float).copy()
        rest = np.flatnonzero(dmax >= radius * inscribed - 1e-6)
        nv = ring.shape[1]
        rel = ring[0] - xy[0]; order = np.argsort(np.arctan2(rel[:, 1], rel[:, 0]))
        for lo in range(0, rest.size, BLOCK):
            r = rest[lo:lo + BLOCK]; pr, gr = p[r], g[r]
            A, D, valid, full = self._planes(ring, xy, bounds[gr], pr)
            k = valid.sum(1)
            vals = np.zeros(r.size)
            for kk in np.unique(k[~full]):
                sel = np.flatnonzero(~full & (k == kk))
                vals[sel] = clip(gr[sel], A[sel, :kk], D[sel, :kk], valid[sel, :kk], xy[pr[sel]])
            sel = np.flatnonzero(full)
            for lo2 in range(0, sel.size, 20000):
                s2 = sel[lo2:lo2 + 20000]
                v0 = ring[pr[s2]][:, order]; v1 = np.roll(v0, -1, axis=1)
                vals[s2] = clip(gr[s2], v0, v1 - v0, np.ones(v0.shape[:2], bool), xy[pr[s2]])
            out[r] = vals
        return out

    def compute(self, points, radii=(100, 250, 500)):
        radii = tuple(radii); nr = len(radii)
        n = len(points); x = {}
        pts = points.to_numpy(); xy = shapely.get_coordinates(pts)
        rmax = max(radii)
        boxes = shapely.box(xy[:, 0] - rmax, xy[:, 1] - rmax, xy[:, 0] + rmax, xy[:, 1] + rmax)
        rings, inscribed = {}, {}
        for radius in radii:
            buffers = points.buffer(radius).to_numpy()
            ring = shapely.get_coordinates(shapely.get_exterior_ring(buffers))
            nv = len(ring) // n - 1
            rings[radius] = (buffers, ring.reshape(n, nv + 1, 2)[:, :nv])
            inscribed[radius] = np.cos(np.pi / nv)
        r_arr = np.array(radii, float); rin_arr = np.array([r * inscribed[r] - 1e-6 for r in radii])

        def cumulative(owner, cls, weights=None):
            """Somma per punto e raggio dei contributi che valgono dal raggio cls in su."""
            ok = cls < nr
            m = np.bincount(owner[ok] * nr + cls[ok], weights=None if weights is None else weights[ok], minlength=n * nr)
            return np.cumsum(m.reshape(n, nr), axis=1)

        for kind, tree, bounds, values in (('road', self.roadtree, self.road_bounds, self.lengths), ('build', self.buildtree, self.build_bounds, self.areas)):
            pairs = tree.query(boxes)
            dmin, dmax = _bbox_dist(bounds[pairs[1]], xy[pairs[0]])
            keep = dmin <= rmax; pairs, dmin, dmax = pairs[:, keep], dmin[keep], dmax[keep]
            # raggio dal quale la geometria è interamente dentro (bbox nel cerchio inscritto)
            cls_in = np.searchsorted(rin_arr, dmax, side='right')
            val = values[pairs[1]]
            if kind == 'road':
                masks = {'all': None, 'major': self.major[pairs[1]], 'motor': self.motor[pairs[1]]}
                full = {k: cumulative(pairs[0], cls_in, val if m is None else val * m) for k, m in masks.items()}
            else:
                full = {'cover': cumulative(pairs[0], cls_in, val)}
            for j, radius in enumerate(radii):
                rest = np.flatnonzero((dmin <= radius) & (cls_in > j))
                pr = pairs[:, rest]
                buffers, ring = rings[radius]
                part = self._measure(kind, xy, buffers, ring, radius, pr, inscribed[radius], all_rest=True)
                if kind == 'road':
                    x[f'road_all_m_{radius}'] = full['all'][:, j] + np.bincount(pr[0], weights=part, minlength=n)
                    for name in ('major', 'motor'):
                        s = masks[name][rest]
                        x[f'road_{name}_m_{radius}'] = full[name][:, j] + np.bincount(pr[0, s], weights=part[s], minlength=n)
                else:
                    x[f'building_cover_{radius}'] = (full['cover'][:, j] + np.bincount(pr[0], weights=part, minlength=n)) / (np.pi * radius ** 2)
        for source, (pois, tree) in self.pois.items():
            c = tree.query(boxes)
            pxy = self._poi_xy[source]
            dist = np.hypot(*(pxy[c[1]] - xy[c[0]]).T)
            cls = np.searchsorted(r_arr, dist, side='left')     # primo raggio con distanza <= raggio
            owner, gcode = c[0], self._poi_group[source][c[1]]
            allc = cumulative(owner, cls)
            ng = len(GROUPS) + 1
            ok = cls < nr
            m = np.bincount((owner[ok] * nr + cls[ok]) * ng + gcode[ok], minlength=n * nr * ng).reshape(n, nr, ng).cumsum(axis=1)
            hours = cumulative(owner, np.where(self._poi_hours[source][c[1]], cls, nr)) if source == 'osm' else None
            for j, radius in enumerate(radii):
                x[f'{source}_poi_all_{radius}'] = allc[:, j].astype(np.int64)
                for gi, group in enumerate(GROUPS):
                    x[f'{source}_{group}_{radius}'] = m[:, j, gi]
                if hours is not None:
                    x[f'osm_hours_known_{radius}'] = hours[:, j].astype(np.int64)
        return pd.DataFrame(x)[self._columns(radii)]

    def _columns(self, radii):
        cols = []
        for radius in radii:
            cols += [f'road_all_m_{radius}', f'road_major_m_{radius}', f'road_motor_m_{radius}', f'building_cover_{radius}']
            for source in self.pois:
                cols.append(f'{source}_poi_all_{radius}')
                cols += [f'{source}_{g}_{radius}' for g in GROUPS]
                if source == 'osm':
                    cols.append(f'osm_hours_known_{radius}')
        return cols


# ---------------------------------------------------------------- esecuzione parallela

_CONTEXT = None


def _memory_gb() -> float | None:
    """Memoria fisica disponibile (Windows: GlobalMemoryStatusEx; altrove /proc/meminfo)."""
    try:
        if os.name == 'nt':
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
            status = MEMORYSTATUSEX(); status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullAvailPhys / 2 ** 30
        for line in open('/proc/meminfo'):
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) / 2 ** 20
    except Exception:
        return None
    return None


def default_workers(input_bytes: int = 0) -> int:
    """Processi: circa i core fisici (metà dei logici), al massimo 8, entro la memoria disponibile."""
    env = os.environ.get('SONAR_FEATURE_WORKERS')
    if env and env.isdigit():
        return max(1, int(env))
    workers = max(1, min(8, (os.cpu_count() or 2) // 2))
    memory = _memory_gb()
    if memory:
        per_worker = 0.6 + 6 * input_bytes / 2 ** 30          # contesto: dati + indici + anelli
        workers = max(1, min(workers, int((memory - 1.5) / per_worker)))
    return workers


def _init_worker(path):
    global _CONTEXT
    data = pd.read_pickle(path)
    _CONTEXT = FastSpatialFeatureContext(*data)


def _work(start, wkb):
    import geopandas as gpd
    points = gpd.GeoSeries(shapely.from_wkb(wkb))
    return start, _CONTEXT.compute(points)


def compute_static_features(receivers, roads, buildings, osm_static, places_static, cfg, cache_dir, workers=None, chunk=1000, log=print):
    """Stessa interfaccia e stessi file di `sonar.prepare.compute_static_features`, calcolo accelerato."""
    from sonar.legacy import reference_features_function
    cache_dir = Path(cache_dir)
    context = FastSpatialFeatureContext(roads, buildings, osm_static, places_static)
    sample_positions = np.linspace(0, len(receivers) - 1, min(100, len(receivers)), dtype=int)
    sample = receivers.geometry.iloc[sample_positions].reset_index(drop=True)
    reference = reference_features_function()(sample, roads, buildings, osm_static, places_static, cfg)
    optimized = context.compute(sample)
    if reference.columns.tolist() != optimized.columns.tolist() or not np.allclose(reference, optimized, rtol=1e-10, atol=1e-7):
        raise AssertionError('Feature accelerate diverse dal riferimento Barcellona')
    max_difference = float(np.max(np.abs(reference.to_numpy() - optimized.to_numpy())))
    log(f'  feature ottimizzate verificate su {len(sample)} ricevitori, differenza massima {max_difference:.3g}')
    cache_dir.mkdir(exist_ok=True)
    chunks = {}
    for path in sorted(cache_dir.glob('*.parquet')):
        try:
            start = int(path.stem); frame = pd.read_parquet(path)
        except Exception:
            continue
        expected = receivers.unit_id.iloc[start:start + chunk].to_numpy()
        if len(frame) == len(expected) and np.array_equal(frame.unit_id.to_numpy(), expected):
            chunks[start] = frame
    if chunks:
        log(f'  ripresi {sum(len(f) for f in chunks.values()):,} ricevitori già calcolati')
    pending = [s for s in range(0, len(receivers), chunk) if s not in chunks]
    data_path = cache_dir / '_contesto.pkl'
    inputs = (roads, buildings, osm_static, places_static)
    pd.to_pickle(inputs, data_path)
    workers = workers or default_workers(data_path.stat().st_size)
    workers = max(1, min(workers, len(pending) or 1))
    started = time.monotonic()
    log(f'  calcolo accelerato su {workers} processi, {len(pending):,} blocchi da {chunk}')

    def store(start, frame):
        frame['unit_id'] = receivers.unit_id.iloc[start:start + chunk].to_numpy()
        tmp = cache_dir / f'{start:07d}.parquet.part'
        frame.to_parquet(tmp, index=False)
        tmp.replace(cache_dir / f'{start:07d}.parquet')
        chunks[start] = frame
        if len(chunks) % 10 == 0 or len(chunks) * chunk >= len(receivers):
            log(f'  feature statiche {sum(len(v) for v in chunks.values()):,} / {len(receivers):,}')

    geoms = receivers.geometry.to_numpy()
    try:
        if workers > 1 and pending:
            import multiprocessing
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                     initializer=_init_worker, initargs=(str(data_path),)) as pool:
                futures = [pool.submit(_work, s, shapely.to_wkb(geoms[s:s + chunk])) for s in pending]
                for future in as_completed(futures):
                    store(*future.result())
            pending = []
    except Exception as exc:   # processi non disponibili: si prosegue nel processo corrente
        log(f'  processi paralleli non disponibili ({type(exc).__name__}: {exc}); calcolo nel processo corrente')
        pending = [s for s in range(0, len(receivers), chunk) if s not in chunks]
    if pending:
        import geopandas as gpd
        with ThreadPoolExecutor(max_workers=2) as pool:
            work = lambda s: (s, context.compute(gpd.GeoSeries(geoms[s:s + chunk])))
            for start, frame in pool.map(work, pending):
                store(start, frame)
    try:
        data_path.unlink()
    except OSError:
        pass
    log(f'  feature statiche calcolate in {time.monotonic() - started:.0f} s')
    spatial = pd.concat([chunks[i] for i in sorted(chunks)], ignore_index=True)
    assert np.array_equal(spatial.unit_id.to_numpy(), receivers.unit_id.to_numpy())
    return spatial, max_difference
