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
 * Object used for populating file trees: node and user file trees.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filesTreePopulator = new qxapp.file.FilesTreePopulator(tree);
 *   filesTreePopulator.populateNodeFiles(nodeId);
 * </pre>
 */

qx.Class.define("qxapp.file.FilesTreePopulator", {
  extend: qx.core.Object,

  construct: function(tree) {
    this.__tree = tree;
  },

  statics: {
    addLoadingChild: function(parent) {
      parent["children"] = [{
        label: "Loading...",
        location: null,
        path: null,
        icon: "qxapp/loading.gif"
      }];
    },

    removeLoadingChild: function(parent) {
      for (let i = parent.getChildren().length - 1; i >= 0; i--) {
        if (parent.getChildren().toArray()[i].getLabel() === "Loading...") {
          parent.getChildren().toArray()
            .splice(i, 1);
        }
      }
    }
  },

  members: {
    __tree: null,

    populateNodeFiles: function(nodeId) {
      const treeName = "Node files";
      this.__resetTree(treeName);

      let store = qxapp.data.Store.getInstance();
      store.addListenerOnce("nodeFiles", e => {
        const files = e.getData();
        this.__filesToTree(files);
      }, this);
      store.getNodeFiles(nodeId);
    },

    populateMyData: function() {
      const treeName = "My Data";
      this.__resetTree(treeName);

      let locationsAdded = [];
      let store = qxapp.data.Store.getInstance();
      store.addListener("myDocuments", e => {
        const {
          location,
          files
        } = e.getData();
        if (!locationsAdded.includes(location)) {
          locationsAdded.push(location);
          this.__filesToTree(files);
        }
      }, this);
      store.getMyDocuments();
    },

    __resetTree: function(treeName) {
      // FIXME: It is not reseting the model
      this.__tree.resetModel();
      const rootData = {
        label: treeName,
        location: null,
        path: null,
        children: []
      };
      const root = qx.data.marshal.Json.createModel(rootData, true);
      this.__tree.setModel(root);
      this.__tree.setDelegate({
        createItem: () => new qxapp.file.FileTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("fileId", "fileId", null, item, id);
          c.bindProperty("location", "location", null, item, id);
          c.bindProperty("path", "path", null, item, id);
          c.bindProperty("size", "size", null, item, id);
        }
      });
    },

    __filesToTree: function(files) {
      const newChildren = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
      this.__addTreeData(newChildren);
    },

    __addTreeData: function(data) {
      let newModelToAdd = qx.data.marshal.Json.createModel(data, true);
      let currentModel = this.__tree.getModel();
      currentModel.getChildren().append(newModelToAdd);
      this.__tree.setModel(currentModel);
      this.__tree.fireEvent("modelChanged");
    }
  }
});
