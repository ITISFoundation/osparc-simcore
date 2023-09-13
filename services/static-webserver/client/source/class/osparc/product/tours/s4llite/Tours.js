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

qx.Class.define("osparc.product.tours.s4llite.Tours", {
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
      }];
    },

    __getDashboardSteps: function() {
      return [{
        anchorEl: "osparc-test-id=studiesTabBtn",
        beforeClick: {
          selector: "osparc-test-id=studiesTabBtn"
        },
        title: "Projects",
        text: "Existing projects can be accessed and managed, and new projects can be created. Each project is represented by a card."
      }, {
        anchorEl: "osparc-test-id=templatesTabBtn",
        beforeClick: {
          selector: "osparc-test-id=templatesTabBtn"
        },
        title: "Tutorials",
        text: "A set of pre-built tutorial projects with results is available to all users. When a tutorial is selected, a copy is automatically created and added to the user’s Projects tab. This new copy is editable."
      }];
    },

    __getStudiesSteps: function() {
      return [{
        anchorEl: "osparc-test-id=startS4LButton",
        beforeClick: {
          selector: "osparc-test-id=studiesTabBtn"
        },
        title: "Starting a New Project",
        text: "Click here if you want to create a new Project."
      }, {
        anchorEl: "osparc-test-id=searchBarFilter-textField-study",
        title: "Project Filter and Search",
        text: "Type here the text of the Project you want to search.<br>Pro tip: click on the field to open filtering options"
      }];
    }
  }
});
