/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */
qx.Class.define("osparc.component.filter.TreeFilter", {
  extend: osparc.component.filter.UIFilter,

  /**
    * @param {string} filterId Group-unique id for the filter.
    * @param {string} filterGroupId Unique group id where the filter belongs.
    * @param {Array} treeData Initialization data
    */
  construct: function(filterId, filterGroupId, treeData = []) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Grow());
    this.__createClassifiersTree(treeData);
  },

  members: {
    __tree: null,

    __createClassifiersTree: function(checkedClassifiers) {
      osparc.utils.Classifiers.getClassifiersAsTree().then(classifiers => {
        this.__tree = new osparc.ui.tree.CheckboxTree(classifiers);
        this.__tree.addListener("checkedChanged", e => {
          this._filterChange(e.getData());
        });
        this._removeAll();
        this._add(this.__tree);

        this.__setCheckedClassifiers(this.__tree.getModel(), checkedClassifiers);
      });
    },

    __setCheckedClassifiers: function(model, checkedClassifiers) {
      if (checkedClassifiers.length === 0) {
        return;
      }

      const nodes = model.getChildren();
      nodes.forEach(node => {
        if ("getData" in node) {
          // this is a leaf
          if (checkedClassifiers.includes(node.getData().getClassifier())) {
            node.setChecked(true);
          }
        } else {
          // this is a branch
          this.__setCheckedClassifiers(node, checkedClassifiers);
        }
      });
    }
  }
});
