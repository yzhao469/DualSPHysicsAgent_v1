"""
Minimal reader for legacy binary VTK particle files produced by DualSPHysics.

Returns particle positions and Idp values used by mass_flow_rate.py.
"""

import re
import numpy as np


_FLOAT_DTYPES = {
    "float": ">f4",
    "double": ">f8",
}

_INT_DTYPES = {
    "char": ">i1",
    "unsigned_char": ">u1",
    "short": ">i2",
    "unsigned_short": ">u2",
    "int": ">i4",
    "unsigned_int": ">u4",
    "long": ">i8",
    "unsigned_long": ">u8",
}


def _require_match(match, message):
    if match is None:
        raise ValueError(message)
    return match


def read_vtk_particles(path):
    """
    Read particle coordinates and Idp from a legacy binary .vtk file.

    Parameters
    ----------
    path : str
        File path to PartFluid_XXXX.vtk.

    Returns
    -------
    dict
        {
            "points": ndarray shape (N, 3), dtype float64,
            "Idp": ndarray shape (N,), dtype int64,
        }
    """
    with open(path, "rb") as f:
        raw = f.read()

    m_points = _require_match(
        re.search(rb"POINTS\s+(\d+)\s+(\w+)\s*(?:\r?\n)", raw),
        f"POINTS section not found in {path}",
    )
    n_points = int(m_points.group(1))
    point_dtype_name = m_points.group(2).decode("ascii").lower()
    point_dtype = _FLOAT_DTYPES.get(point_dtype_name)
    if point_dtype is None:
        raise ValueError(f"Unsupported POINTS dtype: {point_dtype_name}")

    point_count = n_points * 3
    points = np.frombuffer(raw, dtype=point_dtype, count=point_count, offset=m_points.end())
    if points.size != point_count:
        raise ValueError(f"Could not read all POINTS data from {path}")
    points = points.astype(np.float64, copy=False).reshape(n_points, 3)

    m_idp = _require_match(
        re.search(
            rb"SCALARS\s+Idp\s+(\w+)\s*(?:\r?\n)\s*LOOKUP_TABLE\s+\S+\s*(?:\r?\n)",
            raw,
        ),
        f"SCALARS Idp section not found in {path}",
    )
    idp_dtype_name = m_idp.group(1).decode("ascii").lower()
    idp_dtype = _INT_DTYPES.get(idp_dtype_name)
    if idp_dtype is None:
        raise ValueError(f"Unsupported Idp dtype: {idp_dtype_name}")

    idp = np.frombuffer(raw, dtype=idp_dtype, count=n_points, offset=m_idp.end())
    if idp.size != n_points:
        raise ValueError(f"Could not read all Idp data from {path}")

    return {
        "points": points,
        "Idp": idp.astype(np.int64, copy=False),
    }
