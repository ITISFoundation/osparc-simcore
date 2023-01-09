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

qx.Class.define("osparc.component.tutorial.s4llite.S4LLiteUI", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const title = this.tr("Sim4Life Lite: UI");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const introText = this.tr("\
      This is the UI. Enjoy!\
      ");
      const intro = osparc.component.tutorial.Utils.createLabel(introText);
      this._add(intro);

      const dashboardProjects = new qx.ui.basic.Image("osparc/tutorial/s4llite/S4LLiteUI.png").set({
        alignX: "center",
        scale: true,
        width: 723,
        height: 450
      });
      this._add(dashboardProjects);
    }
  }
});
