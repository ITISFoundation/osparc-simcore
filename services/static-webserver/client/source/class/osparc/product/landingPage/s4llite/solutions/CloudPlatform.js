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

qx.Class.define("osparc.product.landingPage.s4llite.solutions.CloudPlatform", {
  extend: osparc.product.landingPage.s4llite.solutions.SolutionsBase,

  members: {
    // override
    buildLayout: function() {
      const title = "All In The Cloud";
      const description = "Experience Most Advanced Simulations ";
      const headerLayout = osparc.product.landingPage.s4llite.solutions.SolutionsBase.createSolutionHeader(title, description);
      this._add(headerLayout);

      [{
        title: "Electromagnetics Full-Wave and Quasi-Static",
        description: "The full-wave 3D electromagnetics solver can be used to simulate complex devices and evaluate SAR or power density exposure on human models; for example in the case of a mobile phone's Bluetooth or 5G antenna.",
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/EM_Phone_Exposure_new.gif",
        imagePos: "left"
      }, {
        title: "Coupled Electromagnetics – Neuro",
        description: "The multi-physics platform seamlessly couples electromagnetic sources with the integrated neuron solver; analyzing for example how a pair of electrodes can stimulate peripherical nerves in a realistic anatomy.",
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/EM_Neuron_new.gif",
        imagePos: "right"
      }, {
        title: "Thermal",
        description: "Powering efficient workflows based on coupled EM-Huygens & Thermal simulations, S4Llite offers an easy and fast way to assess compliance according to the latest ASTM standards.",
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/Thermo_MRILeadPass_new.gif",
        imagePos: "left"
      }, {
        title: "Acoustics",
        description: "S4Llite's acoustic solver is ideally suited for full-wave acoustic propagation modeling in complex anatomical environments. Its image-based modeling capabilities allow to use CT image data to assign heterogeneous bone density and acoustic properties to the skull, e.g., for the in silico assessment of tcFUS-induced in vivo heating.",
        image: "https://zmt.swiss/assets/images/sim4lifeweb/AnimationsFinal/AnimFinal_NewLogo/AcousticHead_new.gif",
        imagePos: "right"
      }, {
        title: "S4L lite Online Access / Web Interface ",
        description: "S4L lite offers students a convenient and accessible simulation experience, accessible from any device and location. With a wealth of tutorials and simulation projects readily available, students can learn and explore at their own pace. Collaboration is also made easy with the ability to share projects with classmates and teachers.",
        image: "https://zmt.swiss/assets/images/sim4lifeweb/Sharing_smaller.gif",
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
