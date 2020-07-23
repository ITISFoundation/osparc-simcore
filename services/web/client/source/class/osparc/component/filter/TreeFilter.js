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
    this.__createTree();
  },
  members: {
    __tree: null,
    __model: null,
    __createTree: function() {
      osparc.utils.Utils.getClassifiersAsTree().then(classifiers => {
        this.__tree = new osparc.ui.tree.CheckboxTree(classifiers);
        this.__tree.addListener("checkedChanged", e => {
          console.log(e.getData());
        });
        this._removeAll();
        this._add(this.__tree);
      });
    }
  }
});
