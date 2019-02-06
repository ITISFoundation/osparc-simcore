/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

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
    // overridden
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

      // Add size
      var sizeWidget = new qx.ui.basic.Label().set({
        width: 70,
        maxWidth: 70,
        textAlign: "right"
      });
      this.bind("size", sizeWidget, "value", {
        converter: function(value) {
          if (value === null) {
            return "";
          }
          return qxapp.utils.Utils.bytesToSize(value);
        }
      });
      this.addWidget(sizeWidget);

      this.addWidget(new qx.ui.core.Spacer(10));

      // Add Path
      var pathWidget = new qx.ui.basic.Label().set({
        width: 300,
        maxWidth: 300,
        textAlign: "right"
      });
      this.bind("path", pathWidget, "value");
      this.addWidget(pathWidget);

      this.addWidget(new qx.ui.core.Spacer(10));

      // Add NodeId
      var fileIdWidget = new qx.ui.basic.Label().set({
        width: 300,
        maxWidth: 300,
        textAlign: "right"
      });
      this.bind("fileId", fileIdWidget, "value");
      this.addWidget(fileIdWidget);
    }
  }
});
