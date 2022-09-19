/* ************************************************************************

   osparc - the simcore frontend

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
 * VirtualTreeItem used by FilesTree
 *
 *   It consists of an entry icon, label, size, path/location and uuid that can be set through props
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.file.FileTreeItem(),
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

qx.Class.define("osparc.file.FileTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this._dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium") + " " +
      qx.locale.Date.getTimeFormat("short")
    );
  },

  properties: {
    location: {
      check: "String",
      event: "changePath",
      nullable: true
    },

    path: {
      check: "String",
      event: "changePath",
      nullable: true
    },

    pathLabel: {
      check: "Array",
      event: "changePathLabel",
      nullable: true
    },

    itemId: {
      check: "String",
      event: "changeItemId",
      apply: "_applyItemId",
      nullable: true
    },

    isDataset: {
      check: "Boolean",
      event: "changeIsDataset",
      init: false,
      nullable: false
    },

    datasetId: {
      check: "String",
      event: "changeDatasetId",
      nullable: true
    },

    loaded: {
      check: "Boolean",
      event: "changeLoaded",
      init: true,
      nullable: false
    },

    fileId: {
      check: "String",
      event: "changeFileId",
      nullable: true
    },

    lastModified: {
      check: "String",
      event: "changeLastModified",
      nullable: true
    },

    size: {
      check: "String",
      event: "changeSize",
      nullable: true
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    _dateFormat: null,

    // overridden
    _addWidgets: function() {
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
        width: 140,
        maxWidth: 140,
        textAlign: "right"
      });
      let that = this;
      this.bind("lastModified", lastModifiedWidget, "value", {
        converter: function(value) {
          if (value === null) {
            return "";
          }
          const date = new Date(value);
          return that._dateFormat.format(date); // eslint-disable-line no-underscore-dangle
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
          return osparc.utils.Utils.bytesToSize(value);
        }
      });
      this.addWidget(sizeWidget);


      const permissions = osparc.data.Permissions.getInstance();
      // Add Path
      const pathWidget = new qx.ui.basic.Label().set({
        width: 300,
        maxWidth: 300,
        textAlign: "right"
      });
      this.bind("path", pathWidget, "value");
      this.addWidget(pathWidget);
      permissions.bind("role", pathWidget, "visibility", {
        converter: () => permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded"
      });

      // Add NodeId
      const fileIdWidget = new qx.ui.basic.Label().set({
        width: 300,
        maxWidth: 300,
        textAlign: "right"
      });
      this.bind("fileId", fileIdWidget, "value");
      this.addWidget(fileIdWidget);
      permissions.bind("role", fileIdWidget, "visibility", {
        converter: () => permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded"
      });
    },

    // override
    _applyItemId: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "fileTreeItem_" + value);
    },

    _applyIcon: function(value, old) {
      this.base(arguments, value, old);
      const icon = this.getChildControl("icon", true);
      if (icon && value === "@FontAwesome5Solid/circle-notch/12") {
        icon.setPadding(0);
        icon.setMarginRight(4);
        icon.getContentElement().addClass("rotate");
      } else {
        icon.resetPadding();
        icon.resetMargin();
        icon.getContentElement().removeClass("rotate");
      }
    }
  },

  destruct: function() {
    this._dateFormat.dispose();
    this._dateFormat = null;
  }
});
