#!/bin/bash 

fail () { 
 echo Execution aborted. 
 read -n1 -r -p "Press any key to continue..." key 
 exit 1 
}

# "name" and "dirout" are named according to the testcase

export name=2D_Hopper
export dirout=${name}_out
export diroutdata=${dirout}/data

# "executables" are renamed and called from their directory

export dirbin=../../../bin/linux
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${dirbin}
export gencase="${dirbin}/GenCase_linux64"
export dualsphysicscpu="${dirbin}/DualSPHysics5.0_NNewtonianCPU_linux64"
export dualsphysicsgpu="${dirbin}/DualSPHysics5.0_NNewtonian_linux64"
export boundaryvtk="${dirbin}/BoundaryVTK_linux64"
export partvtk="${dirbin}/PartVTK_linux64"
export partvtkout="${dirbin}/PartVTKOut_linux64"
export measuretool="${dirbin}/MeasureTool_linux64"
export computeforces="${dirbin}/ComputeForces_linux64"
export isosurface="${dirbin}/IsoSurface_linux64"
export flowtool="${dirbin}/FlowTool_linux64"
export floatinginfo="${dirbin}/FloatingInfo_linux64"

option=1

if [ $option -eq 1 ]; then

${dualsphysicsgpu} -gpu ${dirout}/${name} ${dirout} -dirdataout data -svres
if [ $? -ne 0 ] ; then fail; fi

fi

if [ $option != 3 ];then
 echo All done
 else
 echo Execution aborted
fi

read -n1 -r -p "Press any key to continue..." key
