/* ************************************************************************

   qxapp - the simcore frontend

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
 *     createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
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

qx.Class.define("qxapp.component.widget.inputs.NodeOutputTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);
  },

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
      nullable: false
    },

    key: {
      check: "String",
      nullable: false
    },

    value: {
      nullable: true,
      apply: "_applyValue"
    }
  },

  members : {
    __value: null,
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
    }
  }
});
