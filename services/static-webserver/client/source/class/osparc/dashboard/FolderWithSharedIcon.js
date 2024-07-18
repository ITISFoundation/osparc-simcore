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

    this._createChildControlImpl("folder-icon");
    this._createChildControlImpl("shared-icon");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "folder-icon": {
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/folder/26"
          });
          const iconContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          iconContainer.add(control);
          this._add(iconContainer, {
            height: "100%"
          });
          break;
        }
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
