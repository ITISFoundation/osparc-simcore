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
 *   const filesTreePopulator = new qxapp.file.FilesTreePopulator(tree);
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
      const loadingData = {
        label: "Loading...",
        location: null,
        path: null,
        icon: "qxapp/loading.gif"
      };
      const loadingModel = qx.data.marshal.Json.createModel(loadingData, true);
      parent.getChildren().append(loadingModel);
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
      const rootModel = this.__tree.getModel();
      qxapp.file.FilesTreePopulator.addLoadingChild(rootModel);

      const store = qxapp.data.Store.getInstance();
      store.addListenerOnce("nodeFiles", e => {
        const files = e.getData();
        const newChildren = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
        this.__filesToRoot(newChildren);
      }, this);
      store.getNodeFiles(nodeId);
    },

    populateMyData: function() {
      const treeName = "My Data";
      this.__resetTree(treeName);
      const rootModel = this.__tree.getModel();
      rootModel.getChildren().removeAll();
      qxapp.file.FilesTreePopulator.addLoadingChild(rootModel);

      const store = qxapp.data.Store.getInstance();
      store.addListenerOnce("myLocations", e => {
        const locations = e.getData();
        this.__locationsToRoot(locations);

        for (let i=0; i<locations.length; i++) {
          const locationId = locations[i]["id"];
          this.populateMyLocation(locationId);
        }
      }, this);
      store.getMyLocations();
    },

    populateMyLocation: function(locationId = null) {
      if (locationId) {
        const locationModel = this.__getLocationModel(locationId);
        if (locationModel) {
          locationModel.getChildren().removeAll();
          qxapp.file.FilesTreePopulator.addLoadingChild(locationModel);
        }
      }

      const store = qxapp.data.Store.getInstance();
      store.addListener("myDocuments", ev => {
        const {
          location,
          files
        } = ev.getData();
        this.__filesToLocation(files, location);
      }, this);

      store.getFilesByLocation(locationId);
    },

    addFileEntryToTree: function(fileEntry) {
      const filesData = qxapp.data.Converters.fromDSMToVirtualTreeModel([fileEntry]);
      this.__fileToTree(filesData[0]);
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
          c.bindProperty("lastModified", "lastModified", null, item, id);
          c.bindProperty("size", "size", null, item, id);
          c.bindProperty("icon", "icon", null, item, id);
        }
      });
    },

    __getLocationModel: function(locationId) {
      const rootModel = this.__tree.getModel();
      const locationModels = rootModel.getChildren();
      for (let i=0; i<locationModels.length; i++) {
        const locationModel = locationModels.toArray()[i];
        if (locationModel.getLocation() === locationId || String(locationModel.getLocation()) === locationId) {
          return locationModel;
        }
      }
      return null;
    },

    __locationsToRoot: function(locations) {
      const rootModel = this.__tree.getModel();
      rootModel.getChildren().removeAll();
      for (let i=0; i<locations.length; i++) {
        const location = locations[i];
        const locationData = qxapp.data.Converters.createDirEntry(
          location.name,
          location.id,
          ""
        );
        const locationModel = qx.data.marshal.Json.createModel(locationData, true);
        rootModel.getChildren().append(locationModel);
      }
    },

    __filesToLocation: function(files, locationId) {
      const locationModel = this.__getLocationModel(locationId);
      if (locationModel) {
        locationModel.getChildren().removeAll();
        if (files.length>0) {
          const filesData = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
          for (let j=0; j<filesData[0].children.length; j++) {
            const filesModel = qx.data.marshal.Json.createModel(filesData[0].children[j], true);
            locationModel.getChildren().append(filesModel);
          }
        }
      }
    },

    __filesToRoot: function(data) {
      const currentModel = this.__tree.getModel();
      qxapp.file.FilesTreePopulator.removeLoadingChild(currentModel);

      const newModelToAdd = qx.data.marshal.Json.createModel(data, true);
      currentModel.getChildren().append(newModelToAdd);
      this.__tree.setModel(currentModel);
      this.__tree.fireEvent("modelChanged");
    },

    __fileToTree: function(data) {
      if ("location" in data) {
        const locationModel = this.__getLocationModel(data["location"]);
        if (locationModel && "children" in data && data["children"].length>0) {
          this.__addRecursively(locationModel.getChildren(), data["children"][0]);
        }
      }
    },

    __addRecursively: function(one, two) {
      let newDir = true;
      const oneArray = one.toArray();
      for (let i=0; i<oneArray.length; i++) {
        if ("getPath" in oneArray[i] && oneArray[i].getPath() === two.path) {
          newDir = false;
          if ("children" in two) {
            this.__addRecursively(oneArray[i].getChildren(), two.children[0]);
          }
        }
      }
      if (oneArray.length === 0 || "fileId" in two || newDir) {
        one.append(qx.data.marshal.Json.createModel(two, true));
      }
    }
  }
});
