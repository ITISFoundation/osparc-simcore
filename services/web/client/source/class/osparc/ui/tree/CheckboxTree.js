/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.tree.CheckboxTree", {
  extend: qx.ui.tree.VirtualTree,
  construct: function(data) {
    this.base(arguments, null, "label", "children");
    const model = this.__createModel(data);
    this.setModel(model);
    this.setDelegate({
      createItem: function() {
        return new osparc.ui.tree.CheckboxTreeItem();
      },
      bindItem: function(controller, item, id) {
        controller.bindDefaultProperties(item, id);
        controller.bindProperty("checked", "checked", null, item, id);
        controller.bindPropertyReverse("checked", "checked", null, item, id);
      }
    });
    this.setHideRoot(true);
  },
  members: {
    __createModel: function(data) {
      this.__extendData(data);
      const model = qx.data.marshal.Json.createModel(data, true);
      const enableTriState = node => {
        node.getChildren().forEach(child => {
          enableTriState(child);
          // Binding parent -> child
          node.bind("checked", child, "checked", {
            converter: function(value) {
              if (value === null) {
                // If parent gets null (half-checked), children preserve their values
                return child.getChecked();
              }
              return value;
            }
          });
          child.bind("checked", node, "checked", {
            converter: function() {
              const children = node.getChildren().toArray();
              const areAllChecked = children.every(item => item.getChecked());
              const isOneChecked = children.some(item => item.getChecked() || item.getChecked() === null);
              if (isOneChecked) {
                // Null means half-checked
                return areAllChecked ? true : null;
              }
              return false;
            }
          });
        });
      };
      enableTriState(model);
      return model;
    },
    __extendData: function(data) {
      data.checked = data.checked || false;
      data.children = data.children || [];
      data.children.forEach(child => this.__extendData(child));
    }
  }
});
