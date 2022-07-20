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

qx.Class.define("osparc.dashboard.GridButtonNewPlan", {
  extend: osparc.dashboard.GridButtonNew,

  members: {
    _buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("New Plan"));

      const desc = this.getChildControl("subtitle-text");
      desc.setValue(this.tr("Start a new plan").toString());

      this.setIcon(osparc.dashboard.CardBase.NEW_ICON);
    }
  }
});
