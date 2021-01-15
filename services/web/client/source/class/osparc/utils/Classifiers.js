/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for dealing with Classifiers.
 *
 */

qx.Class.define("osparc.utils.Classifiers", {
  type: "static",

  statics: {
    getClassifiersAsTree: function(reload = false) {
      return new Promise((resolve, reject) => {
        const rootData = {
          label: "root",
          children: []
        };
        osparc.store.Store.getInstance().getAllClassifiers(reload)
          .then(classifiers => {
            const idxs = Object.keys(classifiers);
            if (idxs.length) {
              // Tree-ify
              const tree = {};
              idxs.forEach(idx => this.__buildTree(classifiers, idx, classifiers[idx].key.split("::"), tree));
              rootData.children.push(...this.__virtualTree(tree));
            }
            resolve(rootData);
          });
      });
    },

    // Converts the classifiers to a tree-shaped object
    __buildTree: function(classifiers, classifierId, currentPath, currentNode) {
      const pathName = currentPath.shift();
      if (currentPath.length) {
        currentNode[pathName] = currentNode[pathName] || {};
        this.__buildTree(classifiers, classifierId, currentPath, currentNode[pathName]);
      } else {
        currentNode[pathName] = classifiers[classifierId];
      }
    },

    // Converts the treefied classifiers to a Qooxdoo's VirtualTree friendly format
    __virtualTree: function(currentNode) {
      return Object.entries(currentNode).map(([key, value]) => {
        if (value.classifier) {
          return {
            label: value["display_name"],
            description: value["short_description"],
            url: value["url"],
            data: value
          };
        }
        return {
          label: qx.lang.String.firstUp(key),
          children: this.__virtualTree(currentNode[key])
        };
      });
    },

    getLeafClassifiers: function(classifiers, leaves = []) {
      for (let i=0; i<classifiers.length; i++) {
        const classifier = classifiers[i];
        if (classifier.children.length) {
          this.self().getLeafClassifiers(classifier.children, leaves);
        } else {
          leaves.push(classifier);
        }
      }
      return leaves;
    }
  }
});
