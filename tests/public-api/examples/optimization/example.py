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
from typing import Tuple, Optional, List
from matplotlib import pyplot as plt
from argparse import ArgumentParser
import logging
import osparc

import XCore

import s4l_v1.model as model
import s4l_v1.simulation.emfdtd as fdtd
import s4l_v1.analysis as analysis
import s4l_v1.analysis.viewers as viewers
from s4l_v1._api.application import run_application
import s4l_v1.units as units
import s4l_v1.document as document
import s4l_v1.analysis.extractors as extractors
from s4l_v1.model import Vec3, Translation, Rotation


sys.path.insert(0, Path(__file__).parent)
from solver import OsparcSolver
logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')

class ObjectiveFunction:
	"""
	Objective function which computes the distance of the impedance in a non-blocking way:
	After evaluation it must be polled to check if results are ready.
	"""
	def __init__(self, reference: np.ndarray, cfg: osparc.Configuration) -> None:

		self._reference = reference
		self._cfg = cfg
		self._project_tmp_dir: TemporaryDirectory = TemporaryDirectory()
		self._project_dir: Path = Path(self._project_tmp_dir.name)

		self._sim: Optional[fdtd.Simulation] = None
		self._solver: Optional[OsparcSolver] = None
		self._arm_len: Optional[float] = None

	def __del__(self) -> None:
		self._project_tmp_dir.cleanup()

	def _create_model(self, arm_len: float) -> None:
		"""
		Create model.
		Original (optimal) arm_len = 249.5
		"""

		points = [ Vec3(0,0,0), Vec3(0,5.55,0), Vec3(0,0,arm_len)]

		for i, coordinates in enumerate(points):
			pi = model.CreatePoint(coordinates)
			pi.Name = f'p{i}'

		center = points[0]
		radius = (points[1]-points[0]).Length()

		arm_axis = points[2]-points[0]
		arm1 = model.CreateSolidTube(base_center=points[0], axis_height=arm_axis, major_radius=radius, minor_radius=0, parametrized=True)
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

	def _create_simulation(self, use_graphcard: bool) -> None:

		# retrieve needed entities from model
		entities = model.AllEntities()

		arm1 = entities['Arm 1']
		arm2 = entities['Arm 2']
		source = entities['SourceLine']

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
		self._sim = self._create_simulation(False)
		self._sim.UpdateGrid()
		self._sim.CreateVoxels(str(self._project_dir / 'project.smash'))
		self._sim.WriteInputFile()

		self._solver = OsparcSolver("simcore/services/comp/isolve", "2.1.16", self._cfg)
		self._solver.submit_job(Path(self._sim.InputFilename))
		document.New() # "hack" to reset model

	def result_ready(self) -> bool:
		if self._solver is None:
			return False
		return self._solver.job_done()

	def get_result(self) -> Tuple[float, np.ndarray]:
		if not self.result_ready():
			raise RuntimeError('The result cannot be fetched until results are ready')

		cur_dir : Path = Path.cwd()
		os.chdir(self._project_dir / 'project.smash_Results')
		self._solver.fetch_results(Path(self._sim.OutputFilename), Path(self._sim.InputFilename).parent / 'log.tgz')
		extr = extractors.SimulationExtractor()
		extr.FileName = str(Path(self._sim.OutputFilename).resolve())
		extr.Update()
		impedance = extr['SourceLine'][ 'EM Input Impedance(f)' ]
		impedance.Update()
		sol = np.absolute(np.c_[impedance.Data.Axis, impedance.Data.GetComponent(0)].copy())
		result: float = float(np.linalg.norm(self._reference - sol)**2)
		os.chdir(cur_dir)
		return result, sol

if __name__ == '__main__':
	doc: List[str] = []
	doc.append('In this example we use Sim4Life and oSparc to determine the right length (arm_len) of a dipole antenna in order to achieve a given impedance profile. ')
	doc.append('This is done using a bayesian optimization algorithm which tries to guess the minimum of an objective function which, ')
	doc.append('given an input arm length, outputs the L2 squared distance to the reference impedance profile. I.e. the minimum of the objective function ')
	doc.append('is the arm length giving the wished impedance profile (the optimal armlength is 249.5). N.b. this example should be run with the python interpreter ')
	doc.append('shipped with Sim4Life and several packages must be pip installed into that. This was tested using Sim4Life v. 7.2.')
	parser = ArgumentParser('\n'.join(doc))
	parser.add_argument('username', help='oSparc public API username', type=str)
	parser.add_argument('password', help='oSparc public API password', type=str)
	args = parser.parse_args()

	# run S4L
	XCore.SetLogLevel(XCore.eLogCategory.Warning)
	run_application()
	
	# setup 
	cfg: osparc.Configuration = osparc.Configuration(username=args.username, password=args.password)
	reference_file: Path = Path(__file__).parent / 'reference'
	assert reference_file.is_file(), f'Could not find {reference_file}. It must be located in the same directory as this script.'
	reference = np.absolute(np.loadtxt(reference_file, dtype=np.complex128))

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
				if all(elm == x for elm in res.x) and tmp_guess is not None:
					best_guess = tmp_guess.copy()
				print(20*'-' + f' completed {(n_iter * 100) / (n_batches * batch_size)}% ' + 20*'-')
				n_iter += 1
			else:
				sleep(1)

	print('\n'.join(['Results:', 100*'=', str(res),  100*'=']))
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


