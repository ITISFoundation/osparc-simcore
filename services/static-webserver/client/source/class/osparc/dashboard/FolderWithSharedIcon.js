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

    this.set({
      width: 20,
      alignX: "center"
    });

    this._createChildControlImpl("folder-icon");
    this._createChildControlImpl("shared-icon");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "folder-icon": {
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/folder/20",
            textColor: "green"
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
            textColor: "blue",
            padding: [0, 4]
          });
          this._add(control, {
            bottom: 8,
            right: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
