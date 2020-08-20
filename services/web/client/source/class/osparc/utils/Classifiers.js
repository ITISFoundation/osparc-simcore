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
    getClassifiersAsTree: function() {
      return new Promise((resolve, reject) => {
        const rootData = {
          label: "root",
          children: []
        };
        osparc.store.Store.getInstance().getGroupsOrganizations()
          .then(orgs => {
            if (orgs.length === 0) {
              reject();
              return;
            }
            const classifierPromises = [];
            orgs.forEach(org => {
              const params = {
                url: {
                  "gid": org["gid"]
                }
              };
              classifierPromises.push(osparc.data.Resources.get("classifiers", params));
            });
            Promise.all(classifierPromises)
              .then(classifierss => {
                if (classifierss.length === 0) {
                  reject();
                  return;
                }
                classifierss.forEach(({classifiers}) => {
                  // Converts the classifiers to a tree-shaped object
                  const buildTree = (classifierId, currentPath, currentNode) => {
                    const pathName = currentPath.shift();
                    if (currentPath.length) {
                      currentNode[pathName] = currentNode[pathName] || {};
                      buildTree(classifierId, currentPath, currentNode[pathName]);
                    } else {
                      currentNode[pathName] = classifiers[classifierId];
                    }
                  };
                  // Converts the treefied classifiers to a Qooxdoo's VirtualTree friendly format
                  const virtualTree = currentNode => Object.entries(currentNode).map(([key, value]) => {
                    if (value.classifier) {
                      return {
                        label: value["display_name"],
                        data: value
                      };
                    }
                    return {
                      label: qx.lang.String.firstUp(key),
                      children: virtualTree(currentNode[key])
                    };
                  });
                  const keys = Object.keys(classifiers);
                  if (keys.length) {
                    // Tree-ify
                    const tree = {};
                    keys.forEach(key => buildTree(key, classifiers[key].classifier.split("::"), tree));
                    rootData.children.push(...virtualTree(tree));
                  }
                });
                resolve(rootData);
              });
          });
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
