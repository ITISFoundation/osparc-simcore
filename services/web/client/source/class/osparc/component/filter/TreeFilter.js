/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.filter.TreeFilter", {
  extend: osparc.component.filter.UIFilter,
  construct: function(filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Grow());
    this.__tree = this.__createTree();
    this._add(this.__tree);
  },
  members: {
    __tree: null,
    __model: null,
    __createTree: function() {
      const tree = new osparc.ui.tree.CheckboxTree(classifiers);
      tree.addListener("checkedChanged", e => console.log(e.getData()));
      return tree;
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
