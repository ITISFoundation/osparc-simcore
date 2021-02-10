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
 *   It consists of an entry icon and label and contains more information like: isDir,
 * isRoot, nodeKey, portKey, key.
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
 *       isDir: !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting"),
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
    isDir: {
      check: "Boolean",
      nullable: false,
      init: true
    },

    isRoot: {
      check: "Boolean",
      nullable: false,
      init: false
    },

    nodeKey: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: true
    },

    value: {
      nullable: true,
      event: "changeValue",
      apply: "_applyValue",
      transform: "_transformValue"
    },

    type: {
      check: "String",
      nullable: false
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
      const label = this.__label = new qx.ui.basic.Label();
      this.addWidget(label);
      this.bind("value", label, "visibility", {
        converter: val => typeof val === "string" ? "visible" : "excluded"
      });

      const labelLink = this.__labelLink = new osparc.ui.basic.LinkLabel("", null).set({
        alignY: "middle"
      });
      this.addWidget(labelLink);
      this.bind("value", labelLink, "visibility", {
        converter: val => typeof val === "string" ? "excluded" : "visible"
      });

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });
    },

    _applyValue: async function(value) {
      if (typeof value === "object" && "store" in value) {
        const download = true;
        const locationId = value.store;
        const fileId = value.path;
        const filename = value.filename;
        const presignedLinkData = await osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId);
        if ("presignedLink" in presignedLinkData) {
          this.__labelLink.set({
            value: filename,
            url: presignedLinkData.presignedLink.link
          });
        }
      } else {
        this.__label.setValue(value);
      }
    },

    __isNumber: function(n) {
      return !isNaN(parseFloat(n)) && !isNaN(n - 0);
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
      if (value.getLabel) {
        return value.getLabel();
      }
      if (this.__isNumber(value)) {
        return value.toString();
      }
      return value;
    }
  }
});
