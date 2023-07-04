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

qx.Class.define("osparc.component.reourceUsage.Overview", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__fetchData();
  },

  statics: {
    popUpInWindow: function() {
      const title = qx.locale.Manager.tr("Usage Overview");
      const noteEditor = new osparc.component.reourceUsage.Overview();
      const win = osparc.ui.window.Window.popUpInWindow(noteEditor, title, 325, 256);
      win.center();
      win.open();
      return win;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/paw/14",
            alignX: "center",
            alignY: "middle",
            minWidth: 18
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 3
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchData: function() {

    }
  }
});
