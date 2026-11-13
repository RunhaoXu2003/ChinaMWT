"""JADE coordinate-conversion reference, selectively extracted from data/session.py."""
import numpy as np

def _convert_v1_coords_to_v2(point: np.ndarray, orig_shape: tuple) -> np.ndarray:
    """将 v1 (rot90 k=-1) 坐标转换为 v2 (无旋转) 坐标。

    v1 中 rot90(k=-1) 的映射: 原始(i,j) → v1(row=j, col=H-1-i)
    逆映射: v1(row,col) → 原始(i=H-1-col, j=row)
    """
    H = orig_shape[0]
    row, col = point[0], point[1]
    # v1(row, col) = v1(j, H-1-i) → 其中 i=H-1-col, j=row
    # 在 v2 (原始) 空间中就是 (i, j) = (H-1-col, row)
    return np.array([H - 1.0 - col, row], dtype=np.float64)

def _convert_transposed_coords_to_correct(point: np.ndarray) -> np.ndarray:
    """将转置坐标系中的坐标纠正回正确坐标系。

    旧版程序 bug: 掩膜保存时被 .T 转置，导致 JSON 中 (row, col) 坐标
    的实际含义是 (col, row)。纠正：交换坐标的两个分量。

    即: wrong_coord(row, col) → correct_coord(col, row)
    """
    return np.array([point[1], point[0]], dtype=np.float64)

def _detect_transposed_json(data: dict, orig_shape: tuple) -> bool:
    """检测 JSON 中的坐标是否来自转置后的掩膜（旧版 bug）。

    启发式检测：取所有轮廓控制点和插入点的坐标，若大量点的
    row 坐标 ≥ orig_shape[0]（图像高度），或 col 坐标 ≥ orig_shape[1]（图像宽度），
    则判定为转置坐标系。

    Returns True if coordinates appear to be in transposed coordinate space.
    """
    if orig_shape is None:
        return False
    H, W = orig_shape[0], orig_shape[1]

    all_pts = []
    # 收集控制点
    for cdata in data.get('contours', {}).values():
        cpts = cdata.get('control_points')
        if cpts is not None:
            all_pts.extend(cpts)
    # 收集插入点
    for pt_data in data.get('insertion_points', {}).values():
        if pt_data is not None:
            all_pts.append(pt_data)

    if not all_pts:
        return False

    pts_arr = np.array(all_pts)
    max_row = pts_arr[:, 0].max()
    max_col = pts_arr[:, 1].max()

    # 如果最大 row 接近图像宽度，且最大 col 接近图像高度，判定为转置
    row_exceeds = max_row > H * 1.1  # 允许10%容差（坐标可能落在边界外一点）
    col_exceeds = max_col > W * 1.1

    # 如果 row 没超但 col 超了也不是转置的情况，结合两者判断
    if row_exceeds and not col_exceeds:
        return True

    # 更强信号: row_max 更接近 W 而非 H，且 col_max 更接近 H 而非 W
    if H != W:
        row_is_w = abs(max_row - W) < abs(max_row - H)
        col_is_h = abs(max_col - H) < abs(max_col - W)
        if row_is_w and col_is_h:
            return True

    return False
