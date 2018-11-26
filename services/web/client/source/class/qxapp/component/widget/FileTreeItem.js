/* ************************************************************************

   qxapp - the simcore frontend

   https://simcore.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.component.widget.FileTreeItem", {
  extend : qx.ui.tree.VirtualTreeItem,

  properties : {
    fileId : {
      check : "String",
      event: "changeFileId",
      nullable : true
    },

    path : {
      check : "String",
      event: "changePath",
      nullable : true
    },

    location : {
      check : "String",
      event: "changePath",
      nullable : true
    },

    size : {
      check : "String",
      event: "changeSize",
      nullable : true
    }
  },

  members : {
    _addWidgets : function() {
      // Here's our indentation and tree-lines
      this.addSpacer();
      this.addOpenButton();

      // The standard tree icon follows
      this.addIcon();

      // The label
      this.addLabel();

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Add Path
      var pathWidget = new qx.ui.basic.Label();
      this.bind("path", pathWidget, "value");
      pathWidget.setMaxWidth(300);
      this.addWidget(pathWidget);

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Add NodeId
      var fileIdWidget = new qx.ui.basic.Label();
      this.bind("fileId", fileIdWidget, "value");
      fileIdWidget.setMaxWidth(300);
      this.addWidget(fileIdWidget);

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Add size
      var sizeWidget = new qx.ui.basic.Label();
      this.bind("size", sizeWidget, "value");
      sizeWidget.setMaxWidth(100);
      this.addWidget(sizeWidget);
    }
  }
});
