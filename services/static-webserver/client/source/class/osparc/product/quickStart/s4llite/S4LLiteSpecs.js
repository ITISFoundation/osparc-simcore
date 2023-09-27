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

qx.Class.define("osparc.product.quickStart.s4llite.S4LLiteSpecs", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("<i>S4L<sup>lite</sup></i>: Features and Limitations");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const introText = this.tr("\
        <i>S4L<sup>lite</sup></i> is a powerful web-based simulation platform that allows you to model and analyze real-world phenomena and to \
        design complex technical devices in a validated environment. <i>S4L<sup>lite</sup></i> has been created specifically for students to \
        facilitate their understanding of computational modeling and simulations for various topics, ranging from wireless communication \
        to medical applications. The access to <i>S4L<sup>lite</sup></i> is available free of charge to students enrolled at registered universities.\
      ");
      const intro = osparc.product.quickStart.Utils.createLabel(introText);
      this._add(intro);

      const featuresText = this.tr("\
        <b><i>S4L<sup>lite</sup></i> offers</b><br>\
        - Framework (GUI, Modeling, Postprocessing)<br>\
        - 3D modeling environment (based on the ACIS toolkit) and CAD translators<br>\
        - Postprocessing and visualization of the simulation results (2D and 3D viewers, 2D planar slice, volume rendering, streamlines, surface fields on arbitrary 3D structures, radiation and far-field data)<br>\
        - No restrictions on number of modeling objects<br>\
        - Solvers & Tissue Models:<br>\
        &emsp;- P-EM-FDTD: Electromagnetics Full-Wave Solver<br>\
        &emsp;- P-EM-QS: Quasi-Static Electromagnetics Solver<br>\
        &emsp;- P-Thermal: Thermodynamic Solver<br>\
        &emsp;- P-Acoustics: Acoustics Solver<br>\
        &emsp;- T-Neuro: Neuronal Tissue Models<br>\
        - Computational anatomical model Yoon-sun, the first Korean model of the IT’IS Virtual Population<br>\
        - Material database<br>\
        - Python and Jupyter Notebook scripting\
      ");
      const features = osparc.product.quickStart.Utils.createLabel(featuresText);
      this._add(features);

      const limitationsText = this.tr("\
        <b>Limitations</b><br>\
        The following limitations apply:<br>\
        - Grid size of each simulation is limited to a maximum of <b>20 million grid cells</b><br>\
        - High-Performance Computing is not supported:<br>\
        &emsp;- GPU acceleration is not available<br>\
        &emsp;- MPI multicore acceleration is not available<br>\
        - 3rd-party tools are not available (e.g., MUSAIK, SYSSIM, IMAnalytics, etc…)<br>\
        - Additional ViP models cannot be added<br>\
        - 30 minutes idle time before logout<br>\
        - Hardware resource limits<br>\
        &emsp;- 3 CPUs<br>\
        &emsp;- 3 GB of GPU RAM<br>\
        &emsp;- 5 GB disk space<br>\
        &emsp;- 16 GB RAM<br>\
      ");
      const limitations = osparc.product.quickStart.Utils.createLabel(limitationsText);
      this._add(limitations);
    }
  }
});
