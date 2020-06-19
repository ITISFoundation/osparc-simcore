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
      apply: "_applyValue",
      transform: "_transformValue"
    },

    type: {
      check: "String",
      nullable: false
    }
  },

  members : {
    __valueLabel: null,

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

      // Add the port value
      this.__valueLabel = new qx.ui.basic.Label();
      this.addWidget(this.__valueLabel);
    },

    _applyValue: function(value) {
      this.__valueLabel.setValue(value);
    },

    __isNumber: function(n) {
      return !isNaN(parseFloat(n)) && !isNaN(n - 0);
    },

    _transformValue: function(value) {
      if (value.getLabel) {
        return value.getLabel();
      }
      if (value.getPath) {
        const fileName = value.getPath().split("/");
        if (fileName.length) {
          return fileName[fileName.length-1];
        }
      }
      if (this.__isNumber(value)) {
        return value.toString();
      }
      return value;
    }
  }
});
