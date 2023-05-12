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

qx.Class.define("osparc.product.landingPage.s4llite.solutions.NeuronalActivation", {
  extend: osparc.product.landingPage.s4llite.solutions.SolutionsBase,

  members: {
    // override
    buildLayout: function() {
      const title = "EM-induced Neuronal Dynamics";
      const description = "Modeling Intended and Unintended Neurostimulation by EM-fields";
      const headerLayout = osparc.product.landingPage.s4llite.solutions.SolutionsBase.createSolutionHeader(title, description);
      this._add(headerLayout);

      [{
        title: "Problem Description",
        description: "Electromagnetic fields (EMF) interact with neurons. The interaction can be stimulating, inhibitory, or synchronizing, and it can be intended or unintended. Unintended stimulation by exposure to strong low frequency fields is for example occurring in magnetic resonance imaging (MRI) gradient coils, while examples of intended stimulation include therapeutic applications (transcranial stimulation, deep brain stimulation, functional electrical stimulation, etc.) or neuroprosthetic devices (artificial retina, neuroprosthetic limbs, etc.). Modeling is particularly valuable for treatment and device safety and efficacy assessment, but also to optimize medical device performance.",
        image: "https://zmt.swiss/assets/images/applications/Neuro/_resampled/ResizedImageWzIyMCwxNTBd/MRI-Safety.png",
        imagePos: "left"
      }, {
        title: "Related Standards",
        description: "There are multiple relevant standards regulating EM exposure safety with regard to induced neuronal dynamics: The ICNIRP 2010 exposure guidelines and the IEEE C95.1 exposure standard provide thresholds for general public and occupational exposure to low frequency fields that are based on considerations dominated by the need to prevent adverse EM-neuron interaction-related effects. The IEC 60601-2-33 standard regulates specifically exposure the MRI-related fields.",
        image: "https://zmt.swiss/assets/images/applications/Neuro/_resampled/ResizedImageWzIyMCwxNTBd/Validation2.jpg",
        imagePos: "right"
      }, {
        title: "Coupled EM-Neuronal Dynamics Modeling in Sim4Life",
        description: "The Sim4Life T-NEURO module offers comprehensive neuronal dynamics simulation, full integration and coupling to the EM modeling functionality (P-EM-FDTD and P-EM-QS) of the Sim4Life platform, as well as a range of predefined neuronal dynamics models, including the SENN model underlying the safety standards. A principal strength of Sim4Life is its ability to simulate complex neuronal dynamics models within realistic anatomical models (e.g., the Virtual Population (ViP) 3.0 or models generated from medical image data using the IMG and the iSEG modules). The T-NEURO module is powered by the NEURON solver developed at the Yale University.",
        image: "https://zmt.swiss/assets/images/applications/Neuro/_resampled/ResizedImageWzIyMCwxNTNd/CoupledENNEURO.png",
        imagePos: "left"
      }, {
        title: "Application to Neuroprosthetics",
        description: "Using the T-NEURO functionality of Sim4Life it is possible to investigate implantable electrodes for neuroprosthetic applications. For example, a transverse intrafascicular multichannel electrode (TIME – a neural interface that promises higher stimulation selectivity at the cost of increased invasiveness when compared, e.g., to more common cuff electrodes) design featuring five sub-electrodes to selectively stimulate different neuron groups in the sciatic nerve related to the activation of various muscles was simulated.",
        image: "https://zmt.swiss/assets/images/applications/Neuro/_resampled/ResizedImageWzIyMCwxNTBd/NeuroProsthetics.png",
        imagePos: "right"
      }, {
        title: "Application to Neurostimulation",
        description: "Neurostimulation using external or internal electrodes is applied for various purposes. For example, deep brain stimulation (DBS) uses implanted electrodes to treat movement disorders, depression, etc. Transcranial stimulation uses external electrodes mounted on the head surface, e.g., for stroke rehabilitation. With Sim4Life, it is possible to simulate not only the electric field distribution and currents, but also the related impact on neuronal activity.",
        image: "https://zmt.swiss/assets/images/applications/Neuro/_resampled/ResizedImageWzIyMCwxNTBd/NeuroStimulation.png",
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
