/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.widget.StudyTitleOnlyTree", {
  extend: osparc.component.widget.NodesTree,

  members: {
    populateTree: function() {
      this.base(arguments);
      this.getModel().getChildren().removeAll();
    }
  }
});
