/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.panddy.s4llite.Tours", {
  type: "static",

  statics: {
    getTours: function() {
      return [{
        contextTarget: "osparc-test-id=dashboard",
        name: "Dashboard",
        description: "Introduction to Dashboard tabs",
        steps: this.__getDashboardSteps()
      }, {
        contextTarget: "osparc-test-id=dashboard",
        name: "Projects",
        description: "Introduction to Studies",
        steps: this.__getStudiesSteps()
      }, {
        contextTarget: "osparc-test-id=mode-button-modeling",
        name: "<i>S4L<sup>lite</sup></i>",
        description: "Introduction to Studies",
        steps: this.__getS4LLiteSteps()
      }];
    },

    __getDashboardSteps: function() {
      return [{
        anchorEl: "osparc-test-id=studiesTabBtn",
        action: "execute",
        title: "Projects",
        text: "Existing projects can be accessed and managed, and new projects can be created. Each project is represented by a card."
      }, {
        anchorEl: "osparc-test-id=templatesTabBtn",
        action: "execute",
        title: "Tutorials",
        text: "A set of pre-built tutorial projects with results is available to all users. When a tutorial is selected, a copy is automatically created and added to the user’s Projects tab. This new copy is editable."
      }];
    },

    __getStudiesSteps: function() {
      return [{
        preStep: {
          anchorEl: "osparc-test-id=studiesTabBtn",
          action: "execute"
        },
        anchorEl: "osparc-test-id=startS4LButton",
        title: "Starting a New Project",
        text: "Click here if you want to create a new Project."
      }, {
        anchorEl: "osparc-test-id=searchBarFilter-textField-study",
        title: "Project Filter and Search",
        text: "Type here the text of the Project you want to search.<br>Pro tip: click on the field to open filtering options"
      }];
    },

    __getS4LLiteSteps: function() {
      return [{
        title: "Welcome to The Rocket",
        text: "This is a Proof of Concept"
      }, {
        anchorEl: "osparc-test-id=mode-button-modeling",
        action: "execute",
        title: "Modeling",
        text: "This is the first step in the pipeline. Use our Virtual Population, upload CAD models or build your own model."
      }, {
        anchorEl: "osparc-test-id=mode-button-simulation",
        action: "execute",
        title: "Simulation",
        text: "Simulators, gridders, voxelers and solvers. As you can see, the context chanded so did the avaialble tools."
      }, {
        anchorEl: "osparc-test-id=mode-button-postro",
        action: "execute",
        title: "Post Processing",
        text: "Analyze simulation results and imaging data through advanced visualization and analysis capabilities."
      }];
    }
  }
});
