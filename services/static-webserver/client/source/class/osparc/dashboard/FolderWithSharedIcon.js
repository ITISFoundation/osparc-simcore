/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.FolderWithSharedIcon", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.getChildControl("folder-icon");
    this.getChildControl("shared-icon");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          this._add(control, {
            height: "100%"
          });
          break;
        case "folder-icon":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/folder/26"
          });
          this.getChildControl("icon-container").add(control);
          break;
        case "shared-icon":
          control = new qx.ui.basic.Image().set({
            textColor: "strong-main",
            padding: 0
          });
          this._add(control, {
            bottom: 7,
            left: 2
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
