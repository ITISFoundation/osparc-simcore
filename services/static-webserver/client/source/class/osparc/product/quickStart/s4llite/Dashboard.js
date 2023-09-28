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

qx.Class.define("osparc.product.quickStart.s4llite.Dashboard", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("Dashboard - Projects & Tutorials");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const introText = this.tr("\
        The Dashboard is the place where Projects and Tutorials can be accessed and organized.\
      ");
      const intro = osparc.product.quickStart.Utils.createLabel(introText);
      this._add(intro);

      const dashboardProjects = new qx.ui.basic.Image("https://raw.githubusercontent.com/ZurichMedTech/s4l-lite-manual/main/assets/dashboard/projects.png").set({
        alignX: "center",
        scale: true,
        width: 637,
        height: 301
      });
      this._add(dashboardProjects);

      const newProjectText = this.tr("\
        1) Start <i>S4L<sup>lite</sup></i>: Click the <b>+ Start <i>S4L<sup>lite</sup></i></b> button to create a new project. This will start the user interface of <i>S4L<sup>lite</sup></i>.\
      ");
      const newProject = osparc.product.quickStart.Utils.createLabel(newProjectText);
      this._add(newProject);

      const otherProjectsText = this.tr("\
        2) Other cards: Each card represents an existing project (own projects, or projects shared by other users) that can be accessed and managed. \
        Click on the card to open the project. Click the “three dots” in the upper right corner of the card to perform operations such as rename, share, delete.\
      ");
      const otherProjects = osparc.product.quickStart.Utils.createLabel(otherProjectsText);
      this._add(otherProjects);

      const otherProjects2Text = this.tr("\
        3) TUTORIALS: A set of pre-built read-only tutorial projects with results is available to all <i>S4L<sup>lite</sup></i> users. When a tutorial is selected, a \
        copy is automatically created and added to the user’s Projects tab. This new copy is editable and can be shared.\
      ");
      const otherProjects2 = osparc.product.quickStart.Utils.createLabel(otherProjects2Text);
      this._add(otherProjects2);

      const dashboardTutorials = new qx.ui.basic.Image("https://raw.githubusercontent.com/ZurichMedTech/s4l-lite-manual/main/assets/opensmash.gif").set({
        alignX: "center",
        scale: true,
        width: 627,
        height: 311
      });
      this._add(dashboardTutorials);

      const importProjectsText = this.tr("\
        4) To open an existing desktop project in <i>S4L<sup>lite</sup></i>: \
        - Click the + Start <i>S4L<sup>lite</sup></i> button to create a new project.<br>\
        - Click the menu and select “File Browser…”.<br>\
        - Click “Upload File” for the .smash project and select the file from your desktop. Repeat the same step, but this \
        time select “Upload Folder” and then select the result folder from your desktop. Close the window<br>\
        - Click the Menu again and click “Open” to select the file you just uploaded.<br>\
      ");
      const importProjects = osparc.product.quickStart.Utils.createLabel(importProjectsText);
      this._add(importProjects);
    }
  }
});
