from __future__ import absolute_import
from __future__ import print_function
import sys, os
import numpy as np
from tempfile import TemporaryDirectory
from pathlib import Path
from time import sleep
from skopt import Optimizer
from skopt.plots import plot_gaussian_process
from collections import deque
from typing import Tuple, Optional
from matplotlib import pyplot as plt
from argparse import ArgumentParser
import osparc

import XCore

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
	def __init__(self, reference: np.ndarray, cfg: osparc.Configuration):

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

	def _create_simulation(self, use_graphcard: bool, arm_len: float):

		# retrieve needed entities from model
		entities = model.AllEntities()

		arm1 = entities[f'Arm 1 {arm_len}']
		arm2 = entities[f'Arm 2 {arm_len}']
		source = entities[f'SourceLine {arm_len}']

		# Setup Setttings
		sim = fdtd.Simulation()

		sim.Name = 'Dipole (Broadband)'
		sim.SetupSettings.SimulationTime = 52., units.Periods # Set to e.g. 3 for faster execution time. Correct value: 52

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

	def get_result(self) -> Tuple[float, np.ndarray]:
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
		sol = np.absolute(np.c_[impedance.Data.Axis, impedance.Data.GetComponent(0)].copy())
		result: float = float(np.linalg.norm(self._reference - sol)**2)
		s4l_v1.document.New()
		os.chdir(cur_dir)
		return result, sol

if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument('username', help='oSparc public API username', type=str)
	parser.add_argument('password', help='oSparc public API password', type=str)
	args = parser.parse_args()

	# run S4L
	XCore.SetLogLevel(XCore.eLogCategory.Warning)
	run_application()
	
	# setup 
	cfg: osparc.Configuration = osparc.Configuration(username=args.username, password=args.password)
	reference_file: Path = Path(__file__).parent / 'solution.npy'
	assert reference_file.is_file(), 'Could not find reference file. It must be located in the same directory as this script.'
	reference = np.absolute(np.load(reference_file))

	# run optimization
	opt = Optimizer([(240.0, 260.0)], "GP", acq_func="EI",
					acq_optimizer="sampling",
					initial_point_generator="lhs")

	input_q: deque
	obj_q: deque = deque()

	n_batches: int = 2
	batch_size: int = 5

	res = None
	best_guess: Optional[np.ndarray] = None
	tmp_quess: Optional[np.ndarray] = None

	n_iter: int = 1
	for _ in range(n_batches):
		input_q = deque(elm[0] for elm in opt.ask(batch_size))
		for jj in range(len(input_q)):
			obj = ObjectiveFunction(reference, cfg)
			obj.evaluate(input_q[jj])
			obj_q.append(obj)
		while len(obj_q) > 0:
			if obj_q[0].result_ready():
				x = input_q.popleft()
				obj = obj_q.popleft()
				y, tmp_guess = obj.get_result()
				res = opt.tell([x],y)
				if all( elm == x for elm in res.x) and tmp_guess is not None:
					best_guess = tmp_guess.copy()
				print(20*'-' + f' completed {(n_iter * 100) / (n_batches * batch_size)}% ' + 20*'-')
				n_iter += 1
			else:
				sleep(1)

	print('Results:')
	print(100*'=')
	print(res)
	print(100*'=')
	plot_gaussian_process(res)
	if best_guess is not None:
		# Create a new figure and axes for the second plot
		fig, ax = plt.subplots()
		ax.plot(reference[:,0], reference[:,1], 'r--', label='Reference impedance')
		ax.plot(best_guess[:,0], best_guess[:,1], 'b--', label=f'Impedance w/ arm_len={res.x[0]:.1f})')
		ax.set_xlabel('Frequency [MHz]')
		ax.set_ylabel('EM Input Impedance(f) [V/A]')
		ax.set_title('Dipole Example')
		ax.legend(loc='upper left')
		plt.show(block=True)


