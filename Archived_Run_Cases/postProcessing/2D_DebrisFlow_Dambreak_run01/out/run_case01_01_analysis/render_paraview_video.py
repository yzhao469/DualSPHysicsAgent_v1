from paraview.simple import *
import os
import glob

# -----------------------------
# Paths
# -----------------------------
RUN_DIR = "/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/runs/run_20260328_152600"
PARTICLE_DIR = os.path.join(RUN_DIR, "out", "particles")
OUT_VIDEO = os.path.join(RUN_DIR, "out", "analysis", "debris_paraview_video.mp4")

fluid_files = sorted(glob.glob(os.path.join(PARTICLE_DIR, "PartFluid_*.vtk")))
bound_files = sorted(glob.glob(os.path.join(PARTICLE_DIR, "PartBound_*.vtk")))

if not fluid_files:
    raise RuntimeError("No fluid VTK files found.")
if not bound_files:
    raise RuntimeError("No boundary VTK files found.")

print(f"Found {len(fluid_files)} fluid VTK files")
print(f"Found {len(bound_files)} boundary VTK files")

# -----------------------------
# Load data
# -----------------------------
fluid = LegacyVTKReader(FileNames=fluid_files)
bound = LegacyVTKReader(FileNames=bound_files)

animationScene = GetAnimationScene()
timeKeeper = GetTimeKeeper()
animationScene.UpdateAnimationUsingDataTimeSteps()

renderView = GetActiveViewOrCreate('RenderView')
renderView.ViewSize = [1600, 900]
renderView.Background = [1, 1, 1]

# -----------------------------
# Show fluid
# -----------------------------
fluidDisplay = Show(fluid, renderView, 'UnstructuredGridRepresentation')
fluidDisplay.Representation = 'Point Gaussian'
fluidDisplay.GaussianRadius = 0.18
fluidDisplay.Opacity = 1.0

ColorBy(fluidDisplay, ('POINTS', 'Vel', 'Magnitude'))
fluidDisplay.RescaleTransferFunctionToDataRange(True, False)
fluidDisplay.SetScalarBarVisibility(renderView, True)

fluidLUT = GetColorTransferFunction('Vel')
fluidPWF = GetOpacityTransferFunction('Vel')
fluidLUT.ApplyPreset('Turbo', True)

# -----------------------------
# Show boundary
# -----------------------------
boundDisplay = Show(bound, renderView, 'UnstructuredGridRepresentation')
boundDisplay.Representation = 'Point Gaussian'
boundDisplay.GaussianRadius = 0.18
boundDisplay.Opacity = 1.0

boundary_var = 'Press'
try:
    ColorBy(boundDisplay, ('POINTS', 'Press'))
    boundDisplay.RescaleTransferFunctionToDataRange(True, False)
    boundDisplay.SetScalarBarVisibility(renderView, True)
    boundLUT = GetColorTransferFunction('Press')
    boundLUT.ApplyPreset('Cool to Warm', True)
    print("Boundary colored by Press")
except Exception:
    boundary_var = 'Rhop'
    ColorBy(boundDisplay, ('POINTS', 'Rhop'))
    boundDisplay.RescaleTransferFunctionToDataRange(True, False)
    boundDisplay.SetScalarBarVisibility(renderView, True)
    boundLUT = GetColorTransferFunction('Rhop')
    boundLUT.ApplyPreset('Cool to Warm', True)
    print("Boundary colored by Rhop (Press not available)")

# -----------------------------
# Camera
# -----------------------------
renderView.ResetCamera()
cam = GetActiveCamera()
cam.Elevation(-20)
cam.Azimuth(0)
renderView.ResetCameraClippingRange()

# -----------------------------
# Scalar bars
# -----------------------------
fluidBar = GetScalarBar(fluidLUT, renderView)
fluidBar.Title = 'Fluid Velocity Magnitude'
fluidBar.ComponentTitle = ''
fluidBar.Orientation = 'Horizontal'
fluidBar.WindowLocation = 'Lower Center'

boundBar = GetScalarBar(boundLUT, renderView)
boundBar.Title = 'Boundary Pressure' if boundary_var == 'Press' else 'Boundary Density'
boundBar.ComponentTitle = ''
boundBar.Orientation = 'Vertical'
boundBar.WindowLocation = 'Upper Right Corner'

Render()

# -----------------------------
# Save animation
# -----------------------------
SaveAnimation(
    OUT_VIDEO,
    renderView,
    FrameRate=10
)

print(f"Saved video to: {OUT_VIDEO}")
