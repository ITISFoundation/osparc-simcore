from __future__ import absolute_import
from __future__ import print_function
import sys, os
import numpy as np
from tempfile import TemporaryDirectory
from pathlib import Path
from time import sleep
from skopt import Optimizer
from collections import deque
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


class ObjectiveFunction:
	"""
	Objective function which computes the distance of the impedance in a non-blocking way:
	After evaluation it must be polled to check if results are ready.
	"""
	def __init__(self, reference: np.array, cfg: osparc.Configuration):

		self._reference = reference
		self._cfg = cfg
		self._project_tmp_dir: TemporaryDirectory = TemporaryDirectory()
		self._project_dir: Path = Path(self._project_tmp_dir.name)

		self._sim = None
		self._solver = None
		self._arm_len = None

	def _create_model(self, arm_len: float):
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
		arm1.Name = f'Arm 1 {arm_len}'
		arm2 = arm1.Clone()
		arm2.Name = f'Arm 2 {arm_len}'

		t = arm1.Transform.Translation
		t[2] += 0.5
		arm1.Transform = Translation(t)

		arm2.Transform = Translation(t)
		arm2.Transform = Rotation(axis=Vec3(0,1,0), origin=Vec3(0,0,-arm_len/2), angle_in_rad=np.pi)
		t = arm2.Transform.Translation
		t[2] += arm_len/2 - 0.5
		arm2.Transform = Translation(t)

		source = model.CreatePolyLine( points = [Vec3(0, 0, 0.5), Vec3(0, 0, -0.5)])
		source.Name = f'SourceLine {arm_len}'

	def _create_simulation(self, use_graphcard: bool, arm_len: bool):

		# retrieve needed entities from model
		entities = model.AllEntities()

		arm1 = entities[f'Arm 1 {arm_len}']
		arm2 = entities[f'Arm 2 {arm_len}']
		source = entities[f'SourceLine {arm_len}']

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

	def evaluate(self, arm_len: float) -> None:
		"""
		Evaluate the objective function.
		Input: The armlength
		"""
		self._arm_len = arm_len
		self._create_model(arm_len)
		self._sim = self._create_simulation(False, arm_len)
		self._sim.UpdateGrid()
		self._sim.CreateVoxels(str(self._project_dir / 'project.smash'))
		self._sim.WriteInputFile()

		self._solver = OsparcSolver("simcore/services/comp/isolve", "2.1.16", self._cfg)
		self._solver.submit_job(Path(self._sim.InputFilename))

	def result_ready(self) -> bool:
		if self._solver is None:
			return False
		return self._solver.job_done()

	def get_result(self) -> float:
		assert self.result_ready(), 'The result cannot be fetched until results are ready'
		import s4l_v1.document

		cur_dir : Path = Path.cwd()
		os.chdir(self._project_dir / 'project.smash_Results')
		s4l_v1.document.New()
		s4l_v1.document.AllSimulations.Add(self._sim)

		self._solver.fetch_results(Path(self._sim.OutputFilename), Path(self._sim.InputFilename).parent / 'log.tgz')

		while not self._sim.HasResults():
			sleep(0.5)
		results = self._sim.Results()

		assert self._arm_len is not None, 'arm_len was None. This should not happen'
		impedance = results[f'SourceLine {self._arm_len}'][ 'EM Input Impedance(f)' ]
		impedance.Update()
		sol = np.c_[impedance.Data.Axis, impedance.Data.GetComponent(0)].copy()
		result: float = float(np.linalg.norm(self._reference - sol)**2)
		s4l_v1.document.New()
		os.chdir(cur_dir)
		return result

if __name__ == '__main__':

	# run S4L
	XCore.SetLogLevel(XCore.eLogCategory.Warning)
	run_application()
	
	# setup 
	cfg: osparc.Configuration = osparc.Configuration(username='1c9034e8-713c-5bec-b0ce-6aa070e1b329', password='a1724945-1f91-5dca-8a0c-8efb018028b0')
	reference_file: Path = Path(__file__).parent / 'solution.npy'
	assert reference_file.is_file(), 'Could not find reference file. It must be located in the same directory as this script.'
	reference = np.load(reference_file)

	# run optimization
	opt = Optimizer([(240.0, 260.0)], "GP", acq_func="EI",
					acq_optimizer="sampling",
					initial_point_generator="lhs")

	deque_maxlen: int = 2
	input_q = deque(maxlen=deque_maxlen)
	obj_q = deque(maxlen=deque_maxlen)

	max_n_samples: int = 5

	n_samples: int = 0
	all_inputs = list(elm[0] for elm in opt.ask(max_n_samples))
	res = None
	while n_samples < max_n_samples:
		if len(input_q) < deque_maxlen:
			x = all_inputs[n_samples]
			input_q.append(x)
			obj = ObjectiveFunction(reference, cfg)
			obj.evaluate(x)
			obj_q.append(obj)
			n_samples += 1
		if len(obj_q) > 0 and obj_q[0].result_ready():
			x = input_q.popleft()
			obj = obj_q.popleft()
			y = obj.get_result()
			res = opt.tell([x],y)
			

	print(res)

