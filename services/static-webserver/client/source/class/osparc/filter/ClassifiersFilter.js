/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */
qx.Class.define("osparc.filter.ClassifiersFilter", {
  extend: osparc.filter.UIFilter,

  /**
    * @param {string} filterId Group-unique id for the filter.
    * @param {string} filterGroupId Unique group id where the filter belongs.
    * @param {Array} initTreeData Initialization data
    */
  construct: function(filterId, filterGroupId, initTreeData = []) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Grow());
    this.__createClassifiersTree(initTreeData);
  },

  members: {
    __tree: null,

    recreateTree: function() {
      const checkedClassifiers = this.getCheckedClassifierIDs();
      this.__createClassifiersTree(checkedClassifiers);
    },

    __createClassifiersTree: function(checkedClassifiers, reload = false) {
      osparc.utils.Classifiers.getClassifiersAsTree(reload)
        .then(classifiers => {
          if (classifiers && classifiers.children.length) {
            this.__tree = new osparc.ui.tree.CheckboxTree(classifiers);
            this.__tree.addListener("checkedChanged", e => {
              this._filterChange(e.getData());
            });
            this._removeAll();
            this._add(this.__tree);

            if (checkedClassifiers.length) {
              this.__setCheckedClassifiers(this.__tree.getModel(), checkedClassifiers);
              this._filterChange(this.__tree.getChecked());
            }
          }
        });
    },

    getCheckedClassifierIDs: function() {
      const checkedClassifierIDs = [];
      if (this.__tree) {
        this.__tree.getChecked().forEach(checkedClassifier => {
          if (checkedClassifier.children.length === 0) {
            checkedClassifierIDs.push(checkedClassifier.data.classifier);
          }
        });
      }
      return checkedClassifierIDs;
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
