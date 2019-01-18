/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.DataManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let prjBrowserLayout = new qx.ui.layout.VBox(10);
    this._setLayout(prjBrowserLayout);

    this.__createDataManagerLayout();
    this.__initResources();
  },

  members: {
    __tree: null,

    __initResources: function() {
      this.__tree.populateTree();
    },

    __createDataManagerLayout: function() {
      let dataManagerLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      let vBoxLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      dataManagerLayout.add(vBoxLayout, {
        flex: 1
      });

      let label = new qx.ui.basic.Label(this.tr("Data Manager")).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 150
      });
      vBoxLayout.add(label);

      let filesTree = this.__tree = new qxapp.component.widget.FilesTree().set({
        minHeight: 600
      });
      vBoxLayout.add(filesTree, {
        flex: 1
      });

      this._add(dataManagerLayout);
    }
  }
});
