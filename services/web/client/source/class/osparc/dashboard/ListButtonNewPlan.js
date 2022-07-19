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

qx.Class.define("osparc.dashboard.ListButtonNewPlan", {
  extend: osparc.dashboard.ListButtonNew,

  members: {
    _buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("New Plan"));

      const desc = this.getChildControl("description");
      desc.setValue(this.tr("Start a new plan").toString());

      this.setIcon(osparc.dashboard.CardBase.NEW_ICON);
    }
  }
});
