/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.tutorial.s4llite.S4LLiteSpecs", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const title = this.tr("Sim4Life Lite: Features and Limitations");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const introText = this.tr("\
      Sim4Life Lite is a student edition of Sim4Life and offers a tailored solution for students to to gain insight into the world of \
      computational modeling and simulation. The software is free of charge and can be used to simulate various applications using different \
      physics solvers..\
      ");
      const intro = osparc.component.tutorial.Utils.createLabel(introText);
      this._add(intro);

      const featuresText = this.tr("\
      <b>Features</b><br>\
      This special edition of Sim4Life includes the following features:<br>\
      - Sim4Life framework (GUI, Modeling, Postprocessing)<br>\
      - 3D modeling environment (based on the ACIS toolkit) and CAD translators<br>\
      - Postprocessing and visualization of the simulation results (2D and 3D viewers, 2D planar slice, volume rendering, streamlines, surface fields on arbitrary 3D structures, radiation and far-field data)<br>\
      - No restrictions on number of modeling objects<br>\
      - Solvers and tissue Models<br>\
      - This special edition of Sim4Life includes the following features:<br>\
      &emsp;- P-EM-FDTD: Electromagnetics Full-Wave Solver<br>\
      &emsp;- P-EM-QS: Quasi-Static Electromagnetics Solver<br>\
      &emsp;- P-Thermal: Thermodynamic Solver<br>\
      &emsp;- P-Acoustics: Acoustics Solver<br>\
      &emsp;- T-Neuro: Neuronal Tissue Models<br>\
      - Multi-parameter and multi-goal optimization framework<br>\
      - Computational anatomical model Yoon-sun, the first Korean phantom of the IT’IS Virtual Population<br>\
      - Material database<br>\
      - Python scripting framework\
      ");
      const features = osparc.component.tutorial.Utils.createLabel(featuresText);
      this._add(features);

      const limitationsText = this.tr("\
      <b>Limitations</b><br>\
      The following limitations apply:<br>\
      - Grid size of each simulation is limited to a maximum of <b>20 million grid cells</b><br>\
      - 3rd-party tools are not available (e.g. MUSAIK, SYSSIM, IMAnalytics, etc…)<br>\
      - Additional ViP models cannot be added\
      ");
      const limitations = osparc.component.tutorial.Utils.createLabel(limitationsText);
      this._add(limitations);
    }
  }
});
