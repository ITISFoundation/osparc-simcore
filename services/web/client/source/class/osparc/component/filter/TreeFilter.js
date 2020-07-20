/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.filter.TreeFilter", {
  extend: osparc.component.filter.UIFilter,
  construct: function(filterId, filterGroupId, data) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Grow());
    this.__tree = this.__createTree(data);
    this._add(this.__tree);
  },
  members: {
    __tree: null,
    __model: null,
    __createTree: function(data) {
      data = classifiers;
      this.__model = this.__createModel(data);
      const tree = new qx.ui.tree.VirtualTree(this.__model, "label", "children");
      tree.setDelegate({
        createItem: function() {
          return new osparc.component.filter.TreeFilterItem();
        },
        bindItem: function(controller, item, id) {
          controller.bindDefaultProperties(item, id);
          controller.bindProperty("checked", "checked", null, item, id);
          controller.bindPropertyReverse("checked", "checked", null, item, id);
        }
      });
      tree.setHideRoot(true);
      return tree;
    },
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

const classifiers = {
  label: "root",
  children: [
    {
      label: "Organizations",
      children: [
        {
          label: "IT'IS"
        },
        {
          label: "Speag"
        },
        {
          label: "ZMT"
        }
      ]
    },
    {
      label: "Topics",
      children: [
        {
          label: "Jupyter notebook"
        },
        {
          label: "Python"
        }
      ]
    }
  ]
};
