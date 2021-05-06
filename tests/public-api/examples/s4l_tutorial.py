import os
from pathlib import Path

import s4l_v1
import s4l_v1.analysis.viewers as viewers
import s4l_v1.document as document
import s4l_v1.model as model
import s4l_v1.simulation.emfdtd as fdtd
import s4l_v1.units as units
from dotenv import load_dotenv
from osparc_isolve_api import run_simulation
from s4l_v1._api.application import get_app_safe, run_application
from s4l_v1._api.simwrappers import ApiSimulation
from s4l_v1.model import Vec3

load_dotenv()


HOST = os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006")
KEY = os.environ["OSPARC_API_KEY"]
SECRET = os.environ["OSPARC_API_SECRET"]


def create_model():
    wire = model.CreateWireBlock(
        p0=Vec3(0, 0, 0), p1=Vec3(100, 100, 100), parametrized=True
    )
    wire.Name = "Plane Wave Source"


def create_simulation() -> ApiSimulation:
    # retrieve needed entities from model
    entities = model.AllEntities()

    source_box = entities["Plane Wave Source"]

    sim = fdtd.Simulation()

    sim.Name = "Plane Wave Simulation"
    sim.SetupSettings.SimulationTime = 10.0, units.Periods

    # Materials:
    # No materials

    # Sources
    planesrc_settings = sim.AddPlaneWaveSourceSettings(source_box)
    options = planesrc_settings.ExcitationType.enum
    planesrc_settings.ExcitationType = options.Harmonic
    planesrc_settings.CenterFrequency = 1.0, units.GHz

    # Sensors
    # Only using overall field sensor

    # Boundary Conditions
    options = sim.GlobalBoundarySettings.GlobalBoundaryType.enum
    sim.GlobalBoundarySettings.GlobalBoundaryType = options.UpmlCpml

    # Grid
    manual_grid_settings = sim.AddManualGridSettings([source_box])
    manual_grid_settings.MaxStep = (9.0,) * 3  # model units
    manual_grid_settings.Resolution = (2.0,) * 3  # model units

    # Voxels
    auto_voxel_settings = sim.AddAutomaticVoxelerSettings(source_box)

    # Solver settings
    options = sim.SolverSettings.Kernel.enum
    # sim.SolverSettings.Kernel = options.Software
    sim.SolverSettings.Kernel = options.Cuda
    # FIXME: This does not work. WHY??? sim.SolverSettings.Kernel = options.AXware

    return sim


def analyze_simulation(sim):
    # Create extractor for a given simulation output file
    results = sim.Results()

    # overall field sensor
    overall_field_sensor = results["Overall Field"]

    # Create a slice viewer for the E field
    slice_field_viewer_efield = viewers.SliceFieldViewer()
    slice_field_viewer_efield.Inputs[0].Connect(overall_field_sensor["EM E(x,y,z,f0)"])
    slice_field_viewer_efield.Data.Mode = (
        slice_field_viewer_efield.Data.Mode.enum.QuantityRealPart
    )
    slice_field_viewer_efield.Data.Component = (
        slice_field_viewer_efield.Data.Component.enum.Component0
    )
    slice_field_viewer_efield.Slice.Plane = (
        slice_field_viewer_efield.Slice.Plane.enum.YZ
    )
    slice_field_viewer_efield.Update(0)
    slice_field_viewer_efield.GotoMaxSlice()
    document.AllAlgorithms.Add(slice_field_viewer_efield)


def setup_simulation(smash_path: Path) -> ApiSimulation:
    s4l_v1.document.New()

    create_model()

    sim = create_simulation()

    s4l_v1.document.AllSimulations.Add(sim)
    sim.UpdateGrid()
    sim.CreateVoxels(str(smash_path))
    sim.WriteInputFile()

    return sim


def run(smash_path: Path):
    sim = setup_simulation(smash_path)

    # run using specific version
    # run_simulation(sim, isolve_version="2.0.79", host=HOST, api_key=KEY, api_secret=SECRET)

    # run using latest version
    run_simulation(sim, host=HOST, api_key=KEY, api_secret=SECRET)

    analyze_simulation(sim)


def main():
    if get_app_safe() is None:
        run_application()

    project_dir = Path()
    filename = "em_fdtd_simulation.smash"
    smash_path = project_dir / filename

    run(smash_path)


if __name__ == "__main__":
    main()
