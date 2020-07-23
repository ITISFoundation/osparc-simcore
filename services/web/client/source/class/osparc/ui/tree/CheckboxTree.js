/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A tree that makes its items selectable with a checkbox.
 */
qx.Class.define("osparc.ui.tree.CheckboxTree", {
  extend: qx.ui.tree.VirtualTree,
  construct: function(data) {
    this.base(arguments, this.__createModel(data), "label", "children", "open");
    const tree = this;
    this.set({
      delegate: {
        createItem: function() {
          return new osparc.ui.tree.CheckboxTreeItem();
        },
        bindItem: function(controller, item, id) {
          controller.bindDefaultProperties(item, id);
          controller.bindProperty("checked", "checked", null, item, id);
          controller.bindPropertyReverse("checked", "checked", null, item, id);
        },
        configureItem: function(item) {
          item.addListener("checkboxClicked", () => tree.fireDataEvent("checkedChanged", tree.getChecked()));
          item.setSelectable(false);
        }
      },
      hideRoot: true,
      decorator: "no-border",
      selectionMode: "multi"
    });
  },
  events: {
    checkedChanged: "qx.event.type.Data"
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
          // Binding child -> parent
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
      data.open = data.open || true;
      data.checked = data.checked || false;
      data.children = data.children || [];
      data.children.forEach(child => this.__extendData(child));
    },
    /**
     * Method returning an array of checked elements (model elements).
     * @param {Array?} model Tree model to check. Used for recursion, the method should be called without any parameters.
     */
    getChecked: function(model) {
      const nodes = model == null ? this.getModel().getChildren().toArray() : model.getChildren().toArray();
      let checked = [];
      nodes.forEach(node => {
        if (node.getChecked()) {
          checked.push(node);
        } else {
          checked = [...checked, ...this.getChecked(node)];
        }
      });
      return checked;
    }
  }
});
