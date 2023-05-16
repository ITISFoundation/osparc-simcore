from __future__ import absolute_import
from __future__ import print_function
import sys, os
import numpy as np
from tempfile import TemporaryDirectory
from pathlib import Path
from time import sleep
import osparc

import XCore

import s4l_v1.document as document
import s4l_v1.model as model
import s4l_v1.simulation.emfdtd as fdtd
import s4l_v1.analysis as analysis
import s4l_v1.analysis.viewers as viewers
from s4l_v1._api.application import run_application
import s4l_v1.units as units

sys.path.insert(0, Path(__file__).parent)
from solver import OsparcSolver


def CreateModel(arm_len: float):
	"""
	Create model.
	Original arm_len = 249.5
	"""
	from s4l_v1.model import Vec3, Translation, Rotation

	points = [ Vec3(0,0,0), Vec3(0,5.55,0), Vec3(0,0,arm_len)]

	for i, coordinates in enumerate(points):
		pi = model.CreatePoint(coordinates)
		pi.Name = 'p%i'%i

	center = points[0]
	radius = (points[1]-points[0]).Length()

	arm_axis = points[2]-points[0]
	arm1 = model.CreateSolidTube(base_center=points[0], axis_height=arm_axis, \
		major_radius=radius, minor_radius=0, parametrized=True)
	arm1.Name = 'Arm 1'
	arm2 = arm1.Clone()
	arm2.Name = 'Arm 2'

	t = arm1.Transform.Translation
	t[2] += 0.5
	arm1.Transform = Translation(t)

	arm2.Transform = Translation(t)
	arm2.Transform = Rotation(axis=Vec3(0,1,0), origin=Vec3(0,0,-arm_len/2), angle_in_rad=np.pi)
	t = arm2.Transform.Translation
	t[2] += arm_len/2 - 0.5
	arm2.Transform = Translation(t)

	source = model.CreatePolyLine( points = [Vec3(0, 0, 0.5), Vec3(0, 0, -0.5)])
	source.Name = 'SourceLine'

def CreateSimulation(use_graphcard):

	# retrieve needed entities from model
	entities = model.AllEntities()

	arm1 = entities['Arm 1']
	arm2 = entities['Arm 2']
	source = entities['SourceLine']

	# Setup Setttings
	sim = fdtd.Simulation()

	sim.Name = 'Dipole (Broadband)'
	sim.SetupSettings.SimulationTime = 52., units.Periods #--------------------------- = 52

	options = sim.SetupSettings.GlobalAutoTermination.enum
	sim.SetupSettings.GlobalAutoTermination = options.GlobalAutoTerminationMedium
	
	# Materials:
	dipole_material = sim.AddMaterialSettings([arm1, arm2])
	dipole_material.Name = 'Dipole Arms'
	dipole_material.MaterialType = dipole_material.MaterialType.enum.PEC

	# Sources
	edgesrc_settings = sim.AddEdgeSourceSettings(source)
	options = edgesrc_settings.ExcitationType.enum
	edgesrc_settings.ExcitationType = options.Gaussian
	edgesrc_settings.CenterFrequency = 300., units.MHz
	edgesrc_settings.Bandwidth = 300., units.MHz

	# Sensors
	edgesensor_settings = sim.AddEdgeSensorSettings(source)

	# Boundary Conditions
	options = sim.GlobalBoundarySettings.GlobalBoundaryType.enum
	sim.GlobalBoundarySettings.GlobalBoundaryType = options.UpmlCpml

	# Grid
	global_grid_settings = sim.GlobalGridSettings
	global_grid_settings.DiscretizationMode = global_grid_settings.DiscretizationMode.enum.Manual
	global_grid_settings.MaxStep = np.array([20.0, 20.0, 20.0]), units.MilliMeters
	manual_grid_settings = sim.AddManualGridSettings([arm1, arm2, source])
	manual_grid_settings.MaxStep = (5.0, )*3 # model units
	manual_grid_settings.Resolution = (1.0, )*3  # model units

	# Voxels
	auto_voxel_settings = sim.AddAutomaticVoxelerSettings([arm1, arm2, source])

	# Solver settings
	options = sim.SolverSettings.Kernel.enum
	sim.SolverSettings.Kernel = options.Cuda if use_graphcard else options.Software

	return sim

def objective(arm_len: float, project_dir: Path, reference_sol: np.array, cfg: osparc.Configuration) -> float:
	"""
	Objective function which should be optimized.

	"""
	import s4l_v1.document

	smash_file: Path = Path(project_dir) / 'project.smash'
	
	CreateModel(arm_len)
	
	sim = CreateSimulation(False)
	
	sim.UpdateGrid()
	sim.CreateVoxels(str(smash_file))
	sim.WriteInputFile()

	solver = OsparcSolver("simcore/services/comp/isolve", "2.1.16", cfg)
	solver.submit_job(Path(sim.InputFilename))
	while not solver.job_done():
		sleep(2)

	#=================================================

	cur_dir : Path = Path.cwd()
	os.chdir(project_dir / 'project.smash_Results')

	solver.fetch_results(Path(sim.OutputFilename), Path(sim.InputFilename).parent / 'log.tgz')
	s4l_v1.document.New()
	s4l_v1.document.AllSimulations.Add(sim)
	while not sim.HasResults():
		sleep(1)
	results = sim.Results()

	impedance = results['SourceLine'][ 'EM Input Impedance(f)' ]
	impedance.Update()
	sol = np.c_[impedance.Data.Axis, impedance.Data.GetComponent(0)].copy()
	result: float = float(np.linalg.norm(reference_sol - sol)**2)
	s4l_v1.document.New()
	os.chdir(cur_dir)
	return result

if __name__ == '__main__':
	XCore.SetLogLevel(XCore.eLogCategory.Warning)

	run_application()
	cfg: osparc.Configuration = osparc.Configuration(username='1c9034e8-713c-5bec-b0ce-6aa070e1b329', password='a1724945-1f91-5dca-8a0c-8efb018028b0')
	reference_file: Path = Path(__file__).parent / 'solution.npy'
	assert reference_file.is_file(), 'Could not find reference file. It must be located in the same directory as this script.'
	reference = np.load(reference_file)


	input: float = 249.5
	with TemporaryDirectory() as tmp_dir:
		result = objective(input, Path(tmp_dir), reference, cfg)
		print(f"result = {result}")
	print(f"objective({input}) = {result}")

