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

qx.Class.define("osparc.product.panddy.osparc.Sequences", {
  type: "static",

  statics: {
    getSequences: function() {
      return [{
        id: "dashboard",
        name: "Dashboard",
        description: "Introduction to Dashboard tabs",
        steps: this.__getDashboardSteps()
      }, {
        id: "studies",
        name: "Studies",
        description: "Introduction to Studies",
        steps: this.__getStudiesSteps()
      }];
    },

    __getDashboardSteps: function() {
      return [{
        target: "osparc-test-id=studiesTabBtn",
        action: "execute",
        title: "Studies",
        message: "These are your Studies."
      }, {
        target: "osparc-test-id=templatesTabBtn",
        action: "execute",
        title: "Templates",
        message: "These are the Templates you have access to. If you click on any of the cards listed below, we will create a copy of it so that you can edit it."
      }, {
        target: "osparc-test-id=servicesTabBtn",
        action: "execute",
        title: "Services",
        message: "These are the Services you have access to. Some are computational and others are dynamic. The Computational ones can be run for number crunching and the dynamic ones require user interaction."
      }, {
        target: "osparc-test-id=dataTabBtn",
        action: "execute",
        title: "Data",
        message: "This is the section where you can access all the data you produced or you have access to."
      }];
    },

    __getStudiesSteps: function() {
      return [{
        preStep: {
          target: "osparc-test-id=studiesTabBtn",
          action: "execute"
        },
        target: "osparc-test-id=startS4LButton",
        title: "New Project",
        message: "Click here if you want to create a new Project."
      }, {
        target: "osparc-test-id=searchBarFilter-textField-study",
        title: "Filter Projects",
        message: "Type here the text of the Project you want to search.<br>Pro tip: click on the field to open filtering options"
      }];
    }
  }
});
