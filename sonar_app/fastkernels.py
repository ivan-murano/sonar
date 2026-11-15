"""Nuclei compilati (numba) per le misure a cavallo del bordo dei buffer: stessi conti di `fastfeatures`, più rapidi.

Per ogni coppia ricevitore-geometria: lunghezza dei segmenti stradali (Cyrus-Beck) o area degli anelli degli edifici
(Sutherland-Hodgman) dentro il poligono del buffer, usando i vertici reali del buffer GEOS (64 lati) in coordinate
relative al ricevitore. Se numba non è disponibile `available()` è falso e si usa la versione numpy.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
except Exception:          # numba assente: si usa il percorso numpy
    njit = None


def available() -> bool:
    return njit is not None


if njit is not None:
    @njit(cache=False, nogil=True)
    def _inside(ex, ey, vx, vy, qx, qy, orient):
        return orient * (ex * (qy - vy) - ey * (qx - vx))

    @njit(cache=False, nogil=True)
    def road_lengths(pair_p, pair_g, cx, cy, ring, r_in2, r_out, seg_start, seg_count, sx, sy, ex, ey, out):
        nv = ring.shape[1]
        for k in range(pair_p.shape[0]):
            p = pair_p[k]; g = pair_g[k]
            ox = cx[p]; oy = cy[p]
            # orientamento del poligono (area con segno)
            area2 = 0.0
            for i in range(nv):
                j = (i + 1) % nv
                area2 += (ring[p, i, 0] - ox) * (ring[p, j, 1] - oy) - (ring[p, j, 0] - ox) * (ring[p, i, 1] - oy)
            orient = 1.0 if area2 > 0 else -1.0
            total = 0.0
            for s in range(seg_start[g], seg_start[g] + seg_count[g]):
                ax = sx[s] - ox; ay = sy[s] - oy; bx = ex[s] - ox; by = ey[s] - oy
                dx = bx - ax; dy = by - ay
                length = np.sqrt(dx * dx + dy * dy)
                if length == 0.0:
                    continue
                if ax * ax + ay * ay <= r_in2 and bx * bx + by * by <= r_in2:
                    total += length
                    continue
                # distanza minima del segmento dal centro
                t = -(ax * dx + ay * dy) / (length * length)
                t = min(1.0, max(0.0, t))
                px = ax + t * dx; py = ay + t * dy
                if np.sqrt(px * px + py * py) > r_out:
                    continue
                t0 = 0.0; t1 = 1.0; dead = False
                for i in range(nv):
                    j = (i + 1) % nv
                    vx = ring[p, i, 0] - ox; vy = ring[p, i, 1] - oy
                    wx = ring[p, j, 0] - ox - vx; wy = ring[p, j, 1] - oy - vy
                    fs = _inside(wx, wy, vx, vy, ax, ay, orient)
                    fe = _inside(wx, wy, vx, vy, bx, by, orient)
                    if fs < 0 and fe < 0:
                        dead = True
                        break
                    if fs < 0:
                        t0 = max(t0, fs / (fs - fe))
                    elif fe < 0:
                        t1 = min(t1, fs / (fs - fe))
                if not dead and t1 > t0:
                    total += (t1 - t0) * length
            out[k] = total

    @njit(cache=False, nogil=True)
    def ring_areas(pair_p, pair_g, cx, cy, ring, r_in2, rstart, rcount, ring_order, vstart, vcount, vx_all, vy_all, sign, ring_area, out):
        nv = ring.shape[1]
        maxn = 0
        for r in range(vcount.shape[0]):
            if vcount[r] > maxn:
                maxn = vcount[r]
        cap = 4 * maxn + 4 * nv + 16
        bx = np.empty(cap); by = np.empty(cap); tx = np.empty(cap); ty = np.empty(cap)
        for k in range(pair_p.shape[0]):
            p = pair_p[k]; g = pair_g[k]
            ox = cx[p]; oy = cy[p]
            area2 = 0.0
            for i in range(nv):
                j = (i + 1) % nv
                area2 += (ring[p, i, 0] - ox) * (ring[p, j, 1] - oy) - (ring[p, j, 0] - ox) * (ring[p, i, 1] - oy)
            orient = 1.0 if area2 > 0 else -1.0
            total = 0.0
            for q in range(rstart[g], rstart[g] + rcount[g]):
                rr = ring_order[q]
                m = vcount[rr]
                v0 = vstart[rr]
                far = 0.0
                for i in range(m):
                    bx[i] = vx_all[v0 + i] - ox; by[i] = vy_all[v0 + i] - oy
                    d2 = bx[i] * bx[i] + by[i] * by[i]
                    if d2 > far:
                        far = d2
                if far <= r_in2:
                    total += sign[rr] * ring_area[rr]
                    continue
                n = m
                for e in range(nv):
                    if n == 0:
                        break
                    f = (e + 1) % nv
                    vx = ring[p, e, 0] - ox; vy = ring[p, e, 1] - oy
                    wx = ring[p, f, 0] - ox - vx; wy = ring[p, f, 1] - oy - vy
                    all_in = True
                    for i in range(n):
                        if _inside(wx, wy, vx, vy, bx[i], by[i], orient) < 0:
                            all_in = False
                            break
                    if all_in:
                        continue
                    out_n = 0
                    for i in range(n):
                        sxp = bx[i - 1] if i > 0 else bx[n - 1]
                        syp = by[i - 1] if i > 0 else by[n - 1]
                        fs = _inside(wx, wy, vx, vy, sxp, syp, orient)
                        fe = _inside(wx, wy, vx, vy, bx[i], by[i], orient)
                        if fe >= 0:
                            if fs < 0:
                                t = fs / (fs - fe)
                                tx[out_n] = sxp + t * (bx[i] - sxp); ty[out_n] = syp + t * (by[i] - syp); out_n += 1
                            tx[out_n] = bx[i]; ty[out_n] = by[i]; out_n += 1
                        elif fs >= 0:
                            t = fs / (fs - fe)
                            tx[out_n] = sxp + t * (bx[i] - sxp); ty[out_n] = syp + t * (by[i] - syp); out_n += 1
                        if out_n >= cap - 2:
                            out_n = -1
                            break
                    if out_n < 0:
                        n = -1
                        break
                    for i in range(out_n):
                        bx[i] = tx[i]; by[i] = ty[i]
                    n = out_n
                if n < 0:
                    out[k] = np.nan        # capacità superata: la coppia passa al percorso numpy
                    total = np.nan
                    break
                if n >= 3:
                    a = 0.0
                    for i in range(n):
                        j = (i + 1) % n
                        a += bx[i] * by[j] - bx[j] * by[i]
                    total += sign[rr] * abs(a) / 2.0
            out[k] = total
