/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.utils.FilesTreePopulator", {
  type: "static",

  statics:
  {
    populateMyDocuments: function(tree) {
      const treeName = "My Documents";
      this.__clearTree(tree, treeName);
      let store = qxapp.data.Store.getInstance();

      [
        "MyDocuments",
        "S3PublicDocuments",
        "FakeFiles"
      ].forEach(eventName => {
        if (!store.hasListener(eventName)) {
          store.addListener(eventName, e => {
            const files = e.getData();
            const newChildren = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
            this.__addTreeData(tree, newChildren);
          }, this);
        }
      }, this);

      store.getMyDocuments();
      store.getS3SandboxFiles();
      store.getFakeFiles();
    },

    __clearTree: function(tree, treeName) {
      // FIXME: It is not reseting the model
      tree.resetModel();
      let data = {
        label: treeName,
        children: []
      };
      let emptyModel = qx.data.marshal.Json.createModel(data, true);
      tree.setModel(emptyModel);
      tree.setDelegate({
        createItem: () => new qxapp.component.widget.FileTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("fileId", "fileId", null, item, id);
          c.bindProperty("size", "size", null, item, id);
        }
      });
    },

    __addTreeData: function(tree, data) {
      let newModelToAdd = qx.data.marshal.Json.createModel(data, true);
      let currentModel = tree.getModel();
      currentModel.getChildren().append(newModelToAdd);
      tree.setModel(currentModel);
    }
  }
});
