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

/**
 * VirtualTreeItem used mainly by FilesTreePopulator
 *
 *   It consists of an entry icon, label, size, path/location and uuid that can be set through props
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new qxapp.file.FileTreeItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("fileId", "fileId", null, item, id);
 *       c.bindProperty("location", "location", null, item, id);
 *       c.bindProperty("path", "path", null, item, id);
 *       c.bindProperty("size", "size", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("qxapp.file.FileTreeItem", {
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

    lastModified : {
      check : "String",
      event: "changeLastModified",
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

      // Add lastModified
      const lastModifiedWidget = new qx.ui.basic.Label().set({
        width: 100,
        maxWidth: 100,
        textAlign: "right"
      });
      this.bind("lastModified", lastModifiedWidget, "value", {
        converter: function(value) {
          if (value === null) {
            return "";
          }

          // create a date format like "Oct. 19, 2018 11:31 AM"
          const dateFormat = new qx.util.format.DateFormat(
            qx.locale.Date.getDateFormat("medium") + " " +
            qx.locale.Date.getTimeFormat("short")
          );
          return dateFormat.format(value);
        }
      });
      this.addWidget(lastModifiedWidget);

      // Add size
      const sizeWidget = new qx.ui.basic.Label().set({
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

      if (qxapp.data.Permissions.getInstance().canDo("study.filestree.uuid.read")) {
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
  }
});
