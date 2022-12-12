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

qx.Class.define("osparc.component.tutorial.s4llite.Dashboard", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const title = this.tr("Dashboard - Projects & Tutorials");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const intro = new qx.ui.basic.Label().set({
        value: this.tr("\
        The Dashboard is your private hub which contains all of your Projects as well as Tutorials that have been shared with you. \
        From the Dashboard you are able to open your Project, create a New Project from scratch or create it from a Tutorial.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      });
      this._add(intro);

      const dashboardProjects = new qx.ui.basic.Image("osparc/tutorial/s4llite/Dashboard-Projects.png").set({
        alignX: "center",
        scale: true,
        width: 643,
        height: 205
      });
      this._add(dashboardProjects);

      const newProject = new qx.ui.basic.Label().set({
        value: this.tr("\
        1) Start sim4life: by clicking on this card a new blank project will be created and open.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      });
      this._add(newProject);

      const otherProjects = new qx.ui.basic.Label().set({
        value: this.tr("\
        2) The other cards are Sim4Life projects you created or were shared with you. Click on the casr to resume the work. \
        The three dots button, on the top right corner, will open a menu with many operations like Share, Delete ... and more operations.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      });
      this._add(otherProjects);

      const dashboardTutorials = new qx.ui.basic.Image("osparc/tutorial/s4llite/Dashboard-Tutorials.png").set({
        alignX: "center",
        scale: true,
        width: 644,
        height: 439
      });
      this._add(dashboardTutorials);

      const tutorials = new qx.ui.basic.Label().set({
        value: this.tr("\
        3) Tutorials: there are a series of tutorials projects that illustrate how to use Sim4Life to solve typical simulation problems, \
        and the corresponding documentation.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      });
      this._add(tutorials);
    }
  }
});
