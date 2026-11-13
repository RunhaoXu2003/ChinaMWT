"""Exact scientific functions/constants extracted from the frozen2026-05-02 study script."""
from collections import OrderedDict
import numpy as np
from scipy import ndimage
from scipy.ndimage import binary_dilation,binary_erosion,gaussian_filter
from scipy.interpolate import splprep,splev
from scipy.signal import savgol_filter
from skimage import measure

NUM_THICKNESS_SAMPLES     = 72

CONTOUR_DENSE_SAMPLES     = 720

LABEL_LV_MYO             = 1

LABEL_LV_CAVITY          = 2

LABEL_RV                 = 3

ENDO_DILATE_ITERATIONS   = 1

EPI_ERODE_ITERATIONS     = 0

CONTOUR_SMOOTH_WINDOW    = 15

AHA_16_SEGMENTS = OrderedDict([
    ("MaxLVWT_BasAnt",    (0,   60,  "basal")),
    ("MaxLVWT_BasAntSep", (300, 360, "basal")),
    ("MaxLVWT_BasInfSep", (240, 300, "basal")),
    ("MaxLVWT_BasInf",    (180, 240, "basal")),
    ("MaxLVWT_BasInfLat", (120, 180, "basal")),
    ("MaxLVWT_BasAntLat", (60,  120, "basal")),
    ("MaxLVWT_MidAnt",    (0,   60,  "mid")),
    ("MaxLVWT_MidAntSep", (300, 360, "mid")),
    ("MaxLVWT_MidInfSep", (240, 300, "mid")),
    ("MaxLVWT_MidInf",    (180, 240, "mid")),
    ("MaxLVWT_MidInfLat", (120, 180, "mid")),
    ("MaxLVWT_MidAntLat", (60,  120, "mid")),
    ("MaxLVWT_ApiAnt",    (0,   90,  "apical")),
    ("MaxLVWT_ApiSep",    (270, 360, "apical")),
    ("MaxLVWT_ApiInf",    (180, 270, "apical")),
    ("MaxLVWT_ApiLat",    (90,  180, "apical")),
])

AHA_SHORT = {k: k.replace("MaxLVWT_", "") for k in AHA_16_SEGMENTS}

def find_rvip_pair(mask_data):
    lv_myo = mask_data == LABEL_LV_MYO
    lv_cav = mask_data == LABEL_LV_CAVITY
    rv = mask_data == LABEL_RV
    if not (np.any(lv_myo) and np.any(lv_cav) and np.any(rv)):
        return None, None

    contact = None
    for it in (2, 4, 6, 8, 10):
        lv_d = binary_dilation(lv_myo, iterations=it)
        rv_d = binary_dilation(rv, iterations=it)
        contact = lv_d & rv_d & ~lv_cav
        if np.sum(contact) >= 4:
            break
    if contact is None or np.sum(contact) < 2:
        return None, None

    center = ndimage.center_of_mass(lv_cav)
    pts = np.argwhere(contact)
    dy = pts[:, 0] - center[0]
    dx = pts[:, 1] - center[1]
    angles = np.arctan2(dy, dx)
    idx = np.argsort(angles)
    sa, sp = angles[idx], pts[idx]

    diffs = np.diff(sa)
    wrap = 2 * np.pi - (sa[-1] - sa[0])
    gap = int(np.argmax(np.append(diffs, wrap)))
    n = len(sa)
    if gap < n - 1:
        g1, g2 = sp[:gap + 1], sp[gap + 1:]
    else:
        mid = n // 2
        g1, g2 = sp[:mid], sp[mid:]
    if len(g1) == 0 or len(g2) == 0:
        mid = n // 2
        g1, g2 = sp[:mid], sp[mid:]
    return (tuple(np.mean(g1, axis=0).tolist()),
            tuple(np.mean(g2, axis=0).tolist()))

def assign_anterior_posterior(p1, p2):
    if p1 is None or p2 is None:
        return p1, p2
    return (p1, p2) if p1[1] <= p2[1] else (p2, p1)

def interpolate_rvip(rvip, ordered, frame):
    known = {}
    for si, s in enumerate(ordered):
        k = (s, frame)
        if k in rvip and rvip[k][0] is not None:
            known[si] = rvip[k]
    if not known:
        return rvip
    result = dict(rvip)
    ki = sorted(known)
    for si, s in enumerate(ordered):
        k = (s, frame)
        if k in result and result[k][0] is not None:
            continue
        below = [j for j in ki if j <= si]
        above = [j for j in ki if j >= si]
        if below and above:
            bi, ai = below[-1], above[0]
            if bi == ai:
                pa, pb = known[bi]
            else:
                w = (si - bi) / (ai - bi)
                pa = tuple((np.array(known[bi][0]) * (1 - w)
                            + np.array(known[ai][0]) * w).tolist())
                pb = tuple((np.array(known[bi][1]) * (1 - w)
                            + np.array(known[ai][1]) * w).tolist())
        elif below:
            pa, pb = known[below[-1]]
        elif above:
            pa, pb = known[above[0]]
        else:
            continue
        result[k] = (pa, pb)
    return result

def _jade_find_septum_endpoints(mask_rotated):
    lv_full = (mask_rotated == LABEL_LV_MYO) | (mask_rotated == LABEL_LV_CAVITY)
    rv = mask_rotated == LABEL_RV
    if not (np.any(lv_full) and np.any(rv)):
        return None, None
    lv_boundary = lv_full & ~binary_erosion(lv_full)
    h, w = mask_rotated.shape
    septum = np.zeros_like(lv_boundary)
    for y, x in zip(*np.where(lv_boundary)):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and rv[ny, nx]:
                    septum[y, x] = True
                    break
            if septum[y, x]:
                break
    if np.sum(septum) < 2:
        return None, None
    pts = np.argwhere(septum)
    from itertools import combinations
    best_d, best_pair = 0, (pts[0], pts[1]) if len(pts) >= 2 else (None, None)
    if best_pair[0] is None:
        return None, None
    for a, b in combinations(pts, 2):
        d = np.sum((a - b) ** 2)
        if d > best_d:
            best_d, best_pair = d, (a, b)
    eps = list(best_pair)
    if eps[0][0] < eps[1][0]:
        return eps[0].astype(float), eps[1].astype(float)
    return eps[1].astype(float), eps[0].astype(float)

def extract_smooth_contours(mask, endo_dilate=ENDO_DILATE_ITERATIONS,
                            epi_erode=EPI_ERODE_ITERATIONS):
    """
    Extract and smooth endocardial and epicardial contours.

    Process:
    1. Morphological smoothing of masks:
       - Endocardium: dilate LV cavity (fills papillary muscles/trabeculations)
       - Epicardium: erode LV full mask (smooths outer boundary)
    2. Extract contours using marching squares
    3. B-spline smoothing of contour points

    Returns:
        endo_smooth: (N, 2) array of smoothed endocardial contour [row, col]
        epi_smooth: (M, 2) array of smoothed epicardial contour [row, col]
        centroid: (2,) center of LV cavity [row, col]
    """
    # 迭代次数必须是整数（scipy 要求）；容忍被误设为小数，取整并提示，避免整批静默失败
    try:
        _ei = int(round(float(endo_dilate)))
        _ep = int(round(float(epi_erode)))
    except (TypeError, ValueError):
        _ei, _ep = 0, 0
    if _ei != endo_dilate or _ep != epi_erode:
        print(f"[警告] extract_smooth_contours: 迭代次数须为整数，已把 "
              f"(endo_dilate={endo_dilate}, epi_erode={epi_erode}) 取整为 "
              f"(endo_dilate={_ei}, epi_erode={_ep})")
    endo_dilate, epi_erode = _ei, _ep

    lv_cav = (mask == LABEL_LV_CAVITY).astype(np.uint8)
    lv_full = ((mask == LABEL_LV_MYO) | (mask == LABEL_LV_CAVITY)).astype(np.uint8)

    if np.sum(lv_cav) == 0 or np.sum(lv_full) == 0:
        return None, None, None

    # Centroid of original cavity
    centroid = np.array(ndimage.center_of_mass(lv_cav))

    # --- Morphological smoothing ---
    # Endocardium: dilate cavity to smooth papillary muscles
    if endo_dilate > 0:
        lv_cav_smooth = binary_dilation(lv_cav, iterations=endo_dilate).astype(np.uint8)
        # Gaussian blur then threshold for further smoothing
        lv_cav_smooth = gaussian_filter(lv_cav_smooth.astype(float), sigma=0.8)
        lv_cav_smooth = (lv_cav_smooth > 0.5).astype(np.uint8)
    else:
        lv_cav_smooth = lv_cav

    # Epicardium: erode full mask to smooth outer boundary
    if epi_erode > 0:
        lv_full_smooth = binary_erosion(lv_full, iterations=epi_erode).astype(np.uint8)
        lv_full_smooth = gaussian_filter(lv_full_smooth.astype(float), sigma=0.8)
        lv_full_smooth = (lv_full_smooth > 0.5).astype(np.uint8)
    else:
        lv_full_smooth = lv_full

    # Ensure endo is contained within epi
    lv_full_smooth = np.maximum(lv_full_smooth, lv_cav_smooth)

    # --- Extract contours ---
    endo_cs = measure.find_contours(lv_cav_smooth.astype(float), 0.5)
    epi_cs = measure.find_contours(lv_full_smooth.astype(float), 0.5)

    if not endo_cs or not epi_cs:
        return None, None, None

    endo_raw = max(endo_cs, key=len)
    epi_raw = max(epi_cs, key=len)

    # --- B-spline smoothing ---
    endo_smooth = _smooth_contour_bspline(endo_raw, n_output=360)
    epi_smooth = _smooth_contour_bspline(epi_raw, n_output=360)

    if endo_smooth is None or epi_smooth is None:
        return None, None, None

    return endo_smooth, epi_smooth, centroid

def _smooth_contour_bspline(contour, n_output=360):
    """Smooth a closed contour using periodic B-spline."""
    if len(contour) < 10:
        return None

    # Remove duplicate closing point if present
    if np.allclose(contour[0], contour[-1], atol=0.5):
        contour = contour[:-1]

    if len(contour) < 10:
        return None

    try:
        # Periodic B-spline fitting
        # s (smoothing factor): 0 = interpolating, larger = smoother
        s_factor = len(contour) * 0.5  # Adaptive smoothing
        tck, u = splprep([contour[:, 0], contour[:, 1]],
                         s=s_factor, per=True, k=3)
        # Evaluate at uniform parameter values
        u_new = np.linspace(0, 1, n_output, endpoint=False)
        smooth_pts = splev(u_new, tck)
        return np.column_stack(smooth_pts)
    except Exception:
        # Fallback: Savitzky-Golay filter
        try:
            window = min(CONTOUR_SMOOTH_WINDOW, len(contour) - 1)
            if window % 2 == 0:
                window -= 1
            if window < 5:
                return contour
            # Pad for periodic filtering
            padded_r = np.concatenate([contour[-window:, 0], contour[:, 0], contour[:window, 0]])
            padded_c = np.concatenate([contour[-window:, 1], contour[:, 1], contour[:window, 1]])
            smooth_r = savgol_filter(padded_r, window, 3)[window:-window]
            smooth_c = savgol_filter(padded_c, window, 3)[window:-window]
            return np.column_stack([smooth_r, smooth_c])
        except Exception:
            return contour

def compute_thickness_midline_normal(endo_smooth, epi_smooth, centroid,
                                     anterior_rvip, px_sp=(1.0, 1.0),
                                     n_samples=NUM_THICKNESS_SAMPLES):
    """
    Compute wall thickness using midline-normal method with uniform arc-length spacing.

    Algorithm:
    1. Parameterize endo and epi by angle from centroid → establish correspondence
    2. Compute midline = (endo + epi) / 2 at each angle
    3. Compute arc length of midline, resample uniformly
    4. At each sample, thickness = distance(endo_point, epi_point) in mm
    5. Angles relative to anterior RVIP for AHA segment assignment

    Returns:
        result: dict with keys:
            'thicknesses': (n_samples,) array of thickness values in mm
            'angles_deg': (n_samples,) array of angles in degrees (0=anterior RVIP, CCW)
            'midline_pts': (n_samples, 2) midline points [row, col]
            'endo_pts': (n_samples, 2) corresponding endo points [row, col]
            'epi_pts': (n_samples, 2) corresponding epi points [row, col]
            'max_idx': index of maximum thickness
            'max_thickness': maximum thickness in mm
    """
    # Reference angle from anterior RVIP
    ref_angle = np.arctan2(
        (anterior_rvip[0] - centroid[0]) * px_sp[0],
        (anterior_rvip[1] - centroid[1]) * px_sp[1]
    )

    # --- Step 1: Parameterize by angle from centroid ---
    def contour_to_polar(contour, center):
        dy = contour[:, 0] - center[0]
        dx = contour[:, 1] - center[1]
        angles = np.arctan2(dy, dx)
        r = np.sqrt(dy ** 2 + dx ** 2)
        order = np.argsort(angles)
        return angles[order], r[order], contour[order]

    endo_angles, endo_r, endo_sorted = contour_to_polar(endo_smooth, centroid)
    epi_angles, epi_r, epi_sorted = contour_to_polar(epi_smooth, centroid)

    # --- Step 2: Interpolate to common dense angle sampling ---
    theta_dense = np.linspace(-np.pi, np.pi, CONTOUR_DENSE_SAMPLES, endpoint=False)

    # Circular interpolation using np.interp with period handling
    # Extend for wrap-around
    def circular_interp(theta_target, theta_data, r_data):
        """Interpolate r as function of theta with periodic boundary."""
        # Sort and extend for wrap-around
        idx = np.argsort(theta_data)
        t_s = theta_data[idx]
        r_s = r_data[idx]
        # Extend
        t_ext = np.concatenate([t_s - 2 * np.pi, t_s, t_s + 2 * np.pi])
        r_ext = np.concatenate([r_s, r_s, r_s])
        return np.interp(theta_target, t_ext, r_ext)

    endo_r_dense = circular_interp(theta_dense, endo_angles, endo_r)
    epi_r_dense = circular_interp(theta_dense, epi_angles, epi_r)

    # Ensure epi_r >= endo_r everywhere
    epi_r_dense = np.maximum(epi_r_dense, endo_r_dense + 0.5)

    # Convert back to Cartesian
    endo_dense = np.column_stack([
        centroid[0] + endo_r_dense * np.sin(theta_dense),
        centroid[1] + endo_r_dense * np.cos(theta_dense)
    ])
    epi_dense = np.column_stack([
        centroid[0] + epi_r_dense * np.sin(theta_dense),
        centroid[1] + epi_r_dense * np.cos(theta_dense)
    ])

    # --- Step 3: Compute midline ---
    mid_dense = (endo_dense + epi_dense) / 2.0

    # --- Step 4: Arc-length parameterization of midline ---
    # Compute segment lengths (in mm for proper spacing)
    diff_pts = np.diff(mid_dense, axis=0)
    seg_lengths_mm = np.sqrt(
        (diff_pts[:, 0] * px_sp[0]) ** 2 + (diff_pts[:, 1] * px_sp[1]) ** 2
    )
    arc_cumul = np.concatenate([[0], np.cumsum(seg_lengths_mm)])
    total_arc = arc_cumul[-1]

    # --- Step 5: Resample uniformly by arc length ---
    target_arcs = np.linspace(0, total_arc, n_samples, endpoint=False)

    # Interpolate midline, endo, epi at uniform arc positions
    mid_uniform = np.column_stack([
        np.interp(target_arcs, arc_cumul, mid_dense[:, 0]),
        np.interp(target_arcs, arc_cumul, mid_dense[:, 1])
    ])
    endo_uniform = np.column_stack([
        np.interp(target_arcs, arc_cumul, endo_dense[:, 0]),
        np.interp(target_arcs, arc_cumul, endo_dense[:, 1])
    ])
    epi_uniform = np.column_stack([
        np.interp(target_arcs, arc_cumul, epi_dense[:, 0]),
        np.interp(target_arcs, arc_cumul, epi_dense[:, 1])
    ])

    # --- Step 6: Compute thickness at each sample ---
    thicknesses = np.zeros(n_samples)
    for i in range(n_samples):
        dr = (epi_uniform[i, 0] - endo_uniform[i, 0]) * px_sp[0]
        dc = (epi_uniform[i, 1] - endo_uniform[i, 1]) * px_sp[1]
        thicknesses[i] = np.sqrt(dr ** 2 + dc ** 2)

    # --- Step 7: Compute angles relative to anterior RVIP ---
    angles_abs = np.arctan2(
        (mid_uniform[:, 0] - centroid[0]) * px_sp[0],
        (mid_uniform[:, 1] - centroid[1]) * px_sp[1]
    )
    # Relative to RVIP reference (CCW positive)
    angles_rel = angles_abs - ref_angle
    angles_deg = np.degrees(angles_rel) % 360.0

    # Find maximum
    max_idx = int(np.argmax(thicknesses))
    max_thickness = float(thicknesses[max_idx])

    return {
        'thicknesses': thicknesses,
        'angles_deg': angles_deg,
        'midline_pts': mid_uniform,
        'endo_pts': endo_uniform,
        'epi_pts': epi_uniform,
        'centroid': centroid,
        'max_idx': max_idx,
        'max_thickness': max_thickness,
        'endo_smooth_full': endo_dense,
        'epi_smooth_full': epi_dense,
        'midline_full': mid_dense,
    }

def compute_aha16(thick_data_all, ordered, can_aha):
    """Global max + per-segment max from midline-normal results."""
    g_max = 0.0
    g_pos = "Unknown"

    for s in ordered:
        if s not in thick_data_all:
            continue
        td = thick_data_all[s]
        if td['max_thickness'] > g_max:
            g_max = td['max_thickness']

    seg = OrderedDict((k, "Unknown") for k in AHA_16_SEGMENTS)

    if not can_aha:
        return round(g_max, 2), g_pos, seg

    n = len(ordered)
    c1, c2 = n // 3, 2 * n // 3
    region_sl = {
        "basal": ordered[:c1],
        "mid": ordered[c1:c2],
        "apical": ordered[c2:],
    }

    best_key, best_val = None, 0.0
    for key, (a0, a1, zr) in AHA_16_SEGMENTS.items():
        mx, found = 0.0, False
        for s in region_sl[zr]:
            if s not in thick_data_all:
                continue
            td = thick_data_all[s]
            angles = td['angles_deg']
            thicks = td['thicknesses']
            mask_a = (angles >= a0) & (angles < a1)
            v = thicks[mask_a]
            if len(v):
                mx = max(mx, float(np.max(v)))
                found = True
        if found:
            seg[key] = round(mx, 2)
            if mx > best_val:
                best_val, best_key = mx, key

    if best_key:
        g_pos = AHA_SHORT[best_key]

    return round(g_max, 2), g_pos, seg
