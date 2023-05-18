/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.solutions.Electromagnetics", {
  extend: osparc.product.landingPage.s4llite.solutions.SolutionsBase,

  members: {
    // override
    buildLayout: function() {
      const title = "Electromagnetics";
      const description = "Modeling Vagus Nerve Stimulation";
      const headerLayout = osparc.product.landingPage.s4llite.solutions.SolutionsBase.createSolutionHeader(title, description);
      this._add(headerLayout);

      [{
        title: "Problem Description",
        description: "Vagus nerve stimulation (VNS) was approved in 1997 by the US Food and Drug Administration (FDA) [1] as an invasive neuromodulator approach for the treatment of epilepsy in anti-epileptic drug (AED) resistant subjects. As the vagus nerve (VN) innervates many organs, it is candidate for many new potentially therapeutically relevant applications of selective neurostimulation.",
        image: "https://zmt.swiss/assets/images/applications/VNS/VNS.png",
        imagePos: "left"
      }, {
        title: "Methodology",
        description: "Sim4Life, with its expanded simulative abilities of T-NEURO, permits the investigation of the mechanisms of interaction between EM fields and the electrical activity of neuronal membranes. A wide range of applications ranging from neurostimulation investigations (e.g. transcranial electric (TES) and magnetic (TMS) stimulation), safety (e.g. against peripheral nerve stimulation (PNS) in magnetic resonance imaging (MRI)), as well as the computationally assisted development of electroceuticals or neuroprostetic devices, is now possible. Anatomically realistic compartmentalized electrophysiological representations of axons and neurons modeled using NEURON [3] libraries according to Sim4Life pre-defined biophysical models or available in the web-depository databases – can be positioned within the computational human head/body models to predict the physiological response of nerve and neurons to applied electric (E-) or magnetic (M-) fields.",
        image: "https://zmt.swiss/assets/images/applications/VNS/MIDA.png",
        imagePos: "right"
      }, {
        title: "Modeling of VN Geometry, Electrodes, and EM Simulations",
        description: "Cross-sectional 2D VN models that feature, e.g., epineurium, perineurium, and fascicles, can be created from medical images or scratched in Sim4Life (see Figure top) with the graphical user interface (GUI).  3D models of the VN can be created, for example, by extruding realistic 2D nerve cross sections along user-defined trajectories (see Figure middle), or along anatomical nerve trajectories within computational human models (see Figure bottom) Electrode geometries can be imported in Sim4life as CAD files or created as parameterized model objects even using available templates entities (helical, spiral, etc.).",
        image: "https://zmt.swiss/assets/images/applications/VNS/MIDA.png",
        imagePos: "left"
      }, {
        title: "Creation of Axonal Trajectories and Functionalization",
        description: "Axonal trajectories, created in terms of splines either using the GUI CAD features or numerically using the Python interface can be positioned in the relevant structures (i.e., fascicles) according to user-defined rules (number of axons, length, displacement, etc.) or following realistic nerve trajectories in computational human models. They can be created as well as random spline trajectories within specified entities (for example within fascicles) using the Sim4Life IMSafe tool for implant safety evaluations.",
        image: "https://zmt.swiss/assets/images/applications/VNS/axonaltrajectories.png",
        imagePos: "right"
      }, {
        title: "Post-processing",
        description: "Sim4Life provides multiple options for data visualization (slice and surface view, vector field view and streamline, etc.) including the calculation of E-field related integrals (i.e., flux integrator), the visualization or animation of transmembrane voltages or current profiles. These features can be also used for the visualization of customized post-pro quantities derived from python script (e.g., compound action potentials).",
        image: "https://zmt.swiss/assets/images/applications/VNS/fiberrecruitment.png",
        imagePos: "left"
      }].forEach(contentInfo => {
        const content = osparc.product.landingPage.s4llite.solutions.SolutionsBase.createContent(
          contentInfo.title,
          contentInfo.description,
          contentInfo.image,
          contentInfo.imagePos
        );
        this._add(content);
      });
    }
  }
});
