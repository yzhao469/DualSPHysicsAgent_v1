"""
mass_flow_rate.py
------------------
Computes the mass flow rate of SPH fluid particles through a fixed plane,
using the PartFluid_XXXX.vtk series directly (no need to convert to .txt
first -- this reads the .vtk files straight).

Plane definition
-----------------
Passes through the origin (0,0,0), with one edge along the y-axis. The
other in-plane direction starts along +z and inclines towards +x by
ANGLE_DEG (23 degrees here). That in-plane direction is:

    d = (sin(theta), 0, cos(theta))

so the plane's unit normal (perpendicular to both y and d) is:

    n = (cos(theta), 0, -sin(theta))

The signed distance of a particle at (x,y,z) from the plane is:

    s = n . (x,y,z) = x*cos(theta) - z*sin(theta)

s > 0 is the side the normal points toward; s < 0 is the opposite side.
Flip the sign of `n` below if you want "positive flow" to mean the other
direction.

Method
-------
Each particle keeps the same Idp (ID) across frames as long as it's still
in the domain. For every pair of consecutive frames (dt = 0.2 s apart),
match particles by Idp and check whether the sign of s changed:
    -  ->  +   : one particle-mass crossed in the +n direction
    +  ->  -   : one particle-mass crossed in the -n direction
Net crossings * particle mass / dt gives the mass flow rate for that
0.2 s interval. Particles that leave/enter the domain between frames
(no Idp match) are simply skipped.
"""

import glob
import os
import re
import numpy as np

from vtk_reader import read_vtk_particles

# ---- user settings ---------------------------------------------------
IN_DIR = '.'
PATTERN = 'PartFluid_*.vtk'          # PartFluid_0000.vtk ... PartFluid_0040.vtk
PARTICLE_MASS = 0.000445645          # kg, constant per particle
DT = 0.2                             # s, time between consecutive files
ANGLE_DEG = 23.0                     # plane inclination from +z toward +x
OUT_TXT = 'mass_flow_rate.txt'
# ------------------------------------------------------------------------

theta = np.deg2rad(ANGLE_DEG)
NORMAL = np.array([np.cos(theta), 0.0, -np.sin(theta)])  # unit normal
POINT_ON_PLANE = np.array([0.0, 0.0, 0.0])


def natural_key(path):
    nums = re.findall(r'\d+', os.path.basename(path))
    return int(nums[-1]) if nums else path


def signed_distance(points):
    return (points - POINT_ON_PLANE) @ NORMAL


def net_crossings(prev_ids, prev_side, ids_now, side_now):
    """
    Vectorized match of prev-frame particles to current-frame particles by
    Idp, returns net signed crossing count (positive-direction crossings
    minus negative-direction crossings).
    """
    order = np.argsort(ids_now)
    ids_sorted = ids_now[order]
    side_sorted = side_now[order]

    idx = np.searchsorted(ids_sorted, prev_ids)
    idx = np.clip(idx, 0, len(ids_sorted) - 1)
    matched = ids_sorted[idx] == prev_ids

    side_new = np.full(prev_ids.shape, np.nan)
    side_new[matched] = side_sorted[idx[matched]]

    pos_cross = (prev_side < 0) & (side_new > 0)
    neg_cross = (prev_side > 0) & (side_new < 0)
    return int(pos_cross.sum()) - int(neg_cross.sum())


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, PATTERN)), key=natural_key)
    if len(files) < 2 and IN_DIR == '.':
        # Common layout: VTK files are stored in ./particles.
        files = sorted(glob.glob(os.path.join('particles', PATTERN)), key=natural_key)
    if len(files) < 2:
        print(f'Need at least 2 files matching {PATTERN} in {IN_DIR}')
        return

    times, flow_rates = [], []
    cum_mass = 0.0

    prev_ids = prev_side = None

    for i, f in enumerate(files):
        d = read_vtk_particles(f)
        ids = d['Idp'].astype(np.int64)
        side = np.sign(signed_distance(d['points']))

        if prev_ids is not None:
            crossings = net_crossings(prev_ids, prev_side, ids, side)
            mass_transferred = crossings * PARTICLE_MASS
            flow_rate = mass_transferred / DT
            cum_mass += mass_transferred

            t_mid = (i - 0.5) * DT
            times.append(t_mid)
            flow_rates.append(flow_rate)
            print(f'{os.path.basename(files[i-1])} -> {os.path.basename(f)}  '
                  f'(t={t_mid:5.2f}s): net crossings={crossings:+d}, '
                  f'flow rate={flow_rate:.6e} kg/s')

        prev_ids, prev_side = ids, side

    times = np.array(times)
    flow_rates = np.array(flow_rates)

    print()
    print(f'Total mass crossed the plane (net, +n direction) over '
          f'{times[-1] + DT/2:.2f} s: {cum_mass:.6e} kg')
    print(f'Time-averaged mass flow rate: {flow_rates.mean():.6e} kg/s')

    np.savetxt(OUT_TXT, np.column_stack([times, flow_rates]),
               header='time_s mass_flow_rate_kg_per_s', comments='')
    print(f'Per-interval flow rate written to {OUT_TXT}')


if __name__ == '__main__':
    main()
