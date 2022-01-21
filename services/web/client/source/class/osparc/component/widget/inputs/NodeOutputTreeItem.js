/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * VirtualTreeItem used mainly by NodeOutputTreeItem
 *
 *   It consists of an entry icon and label and contains more information like: nodeKey, portKey, key.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.component.widget.inputs.NodeOutputTreeItem(),
 *     bindItem: (c, item, id) => {
 *      c.bindDefaultProperties(item, id);
 *     },
 *     configureItem: item => {
 *       item.set({
 *       nodeKey: node.getKey(),
 *       portKey: portKey
 *     });
 *   });
 * </pre>
 */

qx.Class.define("osparc.component.widget.inputs.NodeOutputTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,
  include: osparc.ui.tree.MHintInTree,

  properties: {
    type: {
      check: "String",
      nullable: false
    },

    value: {
      nullable: true,
      event: "changeValue",
      apply: "_applyValue",
      transform: "_transformValue"
    },

    nodeKey: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: true
    },

    unitShort: {
      check: "String",
      nullable: true,
      event: "changeUnitShort"
    },

    unitLong: {
      check: "String",
      nullable: true,
      event: "changeUnitLong"
    }
  },

  statics: {
    isNumber: function(n) {
      return !isNaN(parseFloat(n)) && !isNaN(n - 0);
    },

    isBoolean: function(n) {
      return typeof n == "boolean";
    }
  },

  members : {
    __label: null,

    _addWidgets : function() {
      this.addHint().set({
        alignY: "middle"
      });
      this._add(new qx.ui.core.Spacer(5));

      this.addIcon();

      // Add the port label
      const label = this.__label = new qx.ui.basic.Label().set({
        allowGrowX: true
      });
      this.addWidget(label, {
        flex: 1
      });
      this.bind("value", label, "visibility", {
        converter: val => typeof val === "string" ? "visible" : "excluded"
      });

      const labelLink = this.__labelLink = new osparc.ui.basic.LinkLabel("", null).set({
        alignY: "middle",
        allowGrowX: true
      });
      this.addWidget(labelLink, {
        flex: 1
      });
      this.bind("value", labelLink, "visibility", {
        converter: val => typeof val === "string" ? "excluded" : "visible"
      });

      const unitLabel = this.__unitLabel = new qx.ui.basic.Label();
      this.addWidget(unitLabel);
      unitLabel.bind("value", unitLabel, "visibility", {
        converter: val => val === null ? "excluded" : "visible"
      });
      this.bind("unitShort", unitLabel, "value");
      this.bind("unitLong", unitLabel, "toolTipText");
    },

    _applyValue: async function(value) {
      if (typeof value === "object" && "store" in value) {
        // it's a file
        const download = true;
        const locationId = value.store;
        const fileId = value.path;
        const filename = value.filename;
        this.__labelLink.set({
          value: filename
        });
        const presignedLinkData = await osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId);
        if ("presignedLink" in presignedLinkData && presignedLinkData.presignedLink) {
          this.__labelLink.set({
            url: presignedLinkData.presignedLink.link
          });
        }
      } else if (typeof value === "object" && "downloadLink" in value) {
        // it's a link
        const filename = (value.filename && value.filename.length > 0) ? value.filename : osparc.file.FileDownloadLink.extractLabelFromLink(value["downloadLink"]);
        this.__labelLink.set({
          value: filename,
          url: value.downloadLink
        });
      } else if (this.getType() === "array") {
        this.__label.setValue("["+value+"]");
      } else {
        this.__label.setValue(value);
      }
    },

    _transformValue: function(value) {
      if (value.getPath) {
        // it's a file
        const fileName = value.getPath().split("/");
        if (fileName.length) {
          const fn = fileName[fileName.length-1];
          return {
            store: value.getStore(),
            path: value.getPath(),
            filename: fn
          };
        }
      }
      if (value.getDownloadLink) {
        // it's a link
        return {
          downloadLink: value.getDownloadLink(),
          filename: value.getLabel()
        };
      }
      if (value.getLabel) {
        return value.getLabel();
      }
      if (this.self().isNumber(value) || this.self().isBoolean(value)) {
        return value.toString();
      }
      return value;
    }
  }
});
