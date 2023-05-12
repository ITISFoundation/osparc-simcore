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

qx.Class.define("osparc.product.landingPage.s4llite.solutions.Desktop", {
  extend: osparc.product.landingPage.s4llite.solutions.SolutionsBase,

  members: {
    // override
    buildLayout: function() {
      const title = "Desktop";
      const description = "Better stay local";
      const headerLayout = osparc.product.landingPage.s4llite.solutions.SolutionsBase.createSolutionHeader(title, description);
      this._add(headerLayout);

      [{
        title: "Computable Human Phantoms",
        description: "Sim4Life natively supports the Virtual Population ViP 3.x/4.0 models that include integrated posing and morphing tools. Other publicly available animal and human anatomical models are also supported. All tissues are linked to a continually updated physical properties database.",
        image: "https://zmt.swiss/assets/images/sim4life/vipnews.png",
        imagePos: "left"
      }, {
        title: "Physics Solvers",
        description: "The powerful Sim4Life solvers are specifically developed for computationally complex problems; HPC accelerated for the latest computer clusters; and smoothly integrated in the most advanced coupling framework. The platform already includes EM, Thermal Acoustic, and Flow solvers.",
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/_resampled/ResizedImageWzQyMCwyNTFd/EM01.jpg",
        imagePos: "right"
      }, {
        title: "Tissue Models",
        description: "The integrated tissue models enable the modeling and analysis of physiological processes. Perfusion models, tissue damage models, and neuronal models are already included in the first release of Sim4Life.",
        image: "https://zmt.swiss/assets/images/sim4life/tissue_models/_resampled/ResizedImageWzQyMCwyNTBd/neuro01.jpg",
        imagePos: "left"
      }, {
        title: "Framework",
        description: "The Sim4Life Framework efficiently facilitates all steps in complex multiphysics modeling, from defining the problem, discretizing, simulating, and analyzing to visualizing the results, with clarity and flexibility.",
        image: "https://zmt.swiss/assets/images/sim4life/framework/_resampled/ResizedImageWzQyMCwyNTBd/postpro01.jpg",
        imagePos: "right"
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
