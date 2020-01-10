/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * VirtualTree that is able to build its content.
 *
 *   Elements in the tree also accept Drag and/or Drop mechanisms which are implemented here.
 * "osparc-filePath" type is used for the Drag&Drop.
 *
 *   If a file is dropped into a folder, this class will start the copying proccess fireing
 * "fileCopied" event if successful
 *
 * Also provides two static methods for checking whether en entry in the tree is File/Directory
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filesTree = new osparc.file.FilesTree();
 *   this.getRoot().add(filesTree);
 * </pre>
 */

qx.Class.define("osparc.file.FilesTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      decorator: "no-border"
    });

    this.resetChecks();

    this.addListener("tap", this.__selectionChanged, this);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);

    this.__loadPaths = {};
  },

  properties: {
    dragMechnism: {
      check: "Boolean",
      init: false
    },

    dropMechnism: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Event",
    "itemSelected": "qx.event.type.Event",
    "fileCopied": "qx.event.type.Data",
    "filesAddedToTree": "qx.event.type.Event"
  },

  statics: {
    isDir: function(item) {
      let isDir = false;
      if (item["get"+qx.lang.String.firstUp("path")]) {
        if (item.getPath() !== null) {
          isDir = true;
        }
      }
      return isDir;
    },

    isFile: function(item) {
      let isFile = false;
      if (item["set"+qx.lang.String.firstUp("fileId")]) {
        isFile = true;
      }
      return isFile;
    },

    addLoadingChild: function(parent) {
      const loadingModel = new osparc.file.FileTreeItem().set({
        label: "Loading...",
        location: null,
        path: null,
        icon: "@FontAwesome5Solid/circle-notch/12"
      });
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
    __locations: null,
    __datasets: null,
    __loadPaths: null,

    resetChecks: function() {
      this.__locations = new Set();
      this.__datasets = new Set();
    },

    resetCache: function() {
      this.resetChecks();

      const dataStore = osparc.store.Data.getInstance();
      dataStore.resetCache();
    },

    populateNodeTree(nodeId) {
      if (nodeId) {
        this.__populateNodeFiles(nodeId);
      }
    },

    populateTree: function(locationId = null) {
      if (locationId) {
        this.__populateLocation(locationId);
      } else {
        this.__populateLocations();
      }
    },

    loadFilePath: function(outFileVal) {
      const locationId = outFileVal.store;
      let datasetId = "dataset" in outFileVal ? outFileVal.dataset : null;
      const pathId = outFileVal.path;
      if (datasetId === null) {
        const splitted = pathId.split("/");
        if (splitted.length === 3) {
          // simcore.s3
          datasetId = splitted[0];
        }
      }
      this.__addToLoadFilePath(locationId, datasetId, pathId);
      this.__populateLocations();
    },

    __addToLoadFilePath: function(locationId, datasetId, pathId) {
      if (datasetId) {
        if (!(locationId in this.__loadPaths)) {
          this.__loadPaths[locationId] = {};
        }
        if (!(datasetId in this.__loadPaths[locationId])) {
          this.__loadPaths[locationId][datasetId] = new Set();
        }
        this.__loadPaths[locationId][datasetId].add(pathId);
      }
    },

    __hasLocationNeedToBeLoaded: function(locationId) {
      return (locationId in this.__loadPaths) && (Object.keys(this.__loadPaths[locationId]).length > 0);
    },

    __hasDatasetNeedToBeLoaded: function(locationId, datasetId) {
      return (locationId in this.__loadPaths) && (datasetId in this.__loadPaths[locationId]) && (this.__loadPaths[locationId][datasetId].size > 0);
    },

    __filesReceived: function(locationId, datasetId, files) {
      if (this.__hasDatasetNeedToBeLoaded(locationId, datasetId)) {
        const paths = Array.from(this.__loadPaths[locationId][datasetId]);
        for (let i=0; i<paths.length; i++) {
          const path = paths[i];
          for (let j=0; j<files.length; j++) {
            const file = files[j];
            if (file === path) {
              this.__loadPaths[locationId].delete(datasetId);
              return;
            }
          }
        }
      }
    },

    __populateNodeFiles: function(nodeId) {
      const treeName = "Node Files";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      osparc.file.FilesTree.addLoadingChild(rootModel);

      const dataStore = osparc.store.Data.getInstance();
      dataStore.getNodeFiles(nodeId)
        .then(files => {
          const newChildren = osparc.data.Converters.fromDSMToVirtualTreeModel(null, files);
          this.__filesToRoot(newChildren);
          let filesInTree = [];
          this.__getFilesInTree(rootModel, filesInTree);
          for (let i=0; i<filesInTree.length; i++) {
            this.openNodeAndParents(filesInTree[i]);
          }
        });
    },

    __populateLocations: function() {
      this.resetChecks();

      const treeName = "My Data";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      rootModel.getChildren().removeAll();
      osparc.file.FilesTree.addLoadingChild(rootModel);

      const dataStore = osparc.store.Data.getInstance();
      dataStore.getLocations()
        .then(locations => {
          if (this.__locations.size === 0) {
            this.resetChecks();
            this.__locationsToRoot(locations);
            for (let i=0; i<locations.length; i++) {
              const locationId = locations[i]["id"];
              this.__populateLocation(locationId);
            }
          }
        });
    },

    __populateLocation: function(locationId = null) {
      if (locationId !== null) {
        const locationModel = this.__getLocationModel(locationId);
        if (locationModel) {
          locationModel.getChildren().removeAll();
          osparc.file.FilesTree.addLoadingChild(locationModel);
        }
      }

      const dataStore = osparc.store.Data.getInstance();
      dataStore.getDatasetsByLocation(locationId)
        .then(data => {
          const {
            location,
            datasets
          } = data;
          if (location === locationId && !this.__locations.has(locationId)) {
            this.__datasetsToLocation(location, datasets);
          }
        });
    },

    __resetTree: function(treeName) {
      // FIXME: It is not reseting the model
      this.resetModel();
      const rootData = {
        label: treeName,
        itemId: treeName.replace(/\s/g, ""), // remove all whitespaces
        location: null,
        path: null,
        children: []
      };
      const root = qx.data.marshal.Json.createModel(rootData, true);

      this.setModel(root);
      this.setDelegate({
        createItem: () => new osparc.file.FileTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("itemId", "itemId", null, item, id);
          c.bindProperty("fileId", "fileId", null, item, id);
          c.bindProperty("location", "location", null, item, id);
          c.bindProperty("isDataset", "isDataset", null, item, id);
          c.bindProperty("datasetId", "datasetId", null, item, id);
          c.bindProperty("loaded", "loaded", null, item, id);
          c.bindProperty("path", "path", null, item, id);
          c.bindProperty("lastModified", "lastModified", null, item, id);
          c.bindProperty("size", "size", null, item, id);
          c.bindProperty("icon", "icon", null, item, id);
        },
        configureItem: item => {
          const openButton = item.getChildControl("open");
          openButton.addListener("tap", e => {
            if (item.isOpen() && !item.getLoaded() && item.getIsDataset()) {
              item.setLoaded(true);
              const locationId = item.getLocation();
              const datasetId = item.getPath();
              this.__requestDatasetFiles(locationId, datasetId);
            }
          }, this);
          item.addListener("dbltap", e => {
            this.__itemSelected();
          }, this);
          this.__addDragAndDropMechanisms(item);
        }
      });
    },

    __requestDatasetFiles: function(locationId, datasetId) {
      if (this.__datasets.has(datasetId)) {
        return;
      }

      const dataStore = osparc.store.Data.getInstance();
      dataStore.getFilesByLocationAndDataset(locationId, datasetId)
        .then(data => {
          const {
            location,
            dataset,
            files
          } = data;
          this.__filesToDataset(location, dataset, files);
        });
    },

    __getLocationModel: function(locationId) {
      const rootModel = this.getModel();
      const locationModels = rootModel.getChildren();
      for (let i=0; i<locationModels.length; i++) {
        const locationModel = locationModels.toArray()[i];
        if (locationModel.getLocation() === locationId || String(locationModel.getLocation()) === locationId) {
          return locationModel;
        }
      }
      return null;
    },

    __getDatasetModel: function(locationId, datasetId) {
      const locationModel = this.__getLocationModel(locationId);
      const datasetModels = locationModel.getChildren();
      for (let i=0; i<datasetModels.length; i++) {
        const datasetModel = datasetModels.toArray()[i];
        if (datasetModel.getPath() === datasetId || String(datasetModel.getPath()) === datasetId) {
          return datasetModel;
        }
      }
      return null;
    },

    __locationsToRoot: function(locations) {
      const rootModel = this.getModel();
      rootModel.getChildren().removeAll();
      let openThis = null;
      for (let i=0; i<locations.length; i++) {
        const location = locations[i];
        const locationData = osparc.data.Converters.createDirEntry(
          location.name,
          location.id,
          ""
        );
        const locationModel = qx.data.marshal.Json.createModel(locationData, true);
        rootModel.getChildren().append(locationModel);
        if (this.__hasLocationNeedToBeLoaded(location.id)) {
          openThis = locationModel;
        }
      }
      if (openThis) {
        this.openNodeAndParents(openThis);
      }
    },

    __datasetsToLocation: function(locationId, datasets) {
      const dataStore = osparc.store.Data.getInstance();

      const locationModel = this.__getLocationModel(locationId);
      if (!locationModel) {
        return;
      }
      this.__locations.add(locationId);
      locationModel.getChildren().removeAll();
      let openThis = null;
      for (let i=0; i<datasets.length; i++) {
        const dataset = datasets[i];
        const datasetData = osparc.data.Converters.createDirEntry(
          dataset.display_name,
          locationId,
          dataset.dataset_id,
        );
        datasetData.isDataset = true;
        datasetData.loaded = false;
        const datasetModel = qx.data.marshal.Json.createModel(datasetData, true);
        osparc.file.FilesTree.addLoadingChild(datasetModel);
        locationModel.getChildren().append(datasetModel);

        // add cached files
        const datasetId = dataset.dataset_id;
        const cachedData = dataStore.getFilesByLocationAndDatasetCached(locationId, datasetId);
        if (cachedData) {
          this.__filesToDataset(cachedData.location, cachedData.dataset, cachedData.files);
        }

        if (this.__hasDatasetNeedToBeLoaded(locationId, datasetId)) {
          openThis = datasetModel;
        }
      }
      if (openThis) {
        const datasetId = openThis.getItemId();
        this.openNodeAndParents(openThis);
        this.__requestDatasetFiles(locationId, datasetId);
      }
    },

    __filesToDataset: function(locationId, datasetId, files) {
      if (this.__datasets.has(datasetId)) {
        return;
      }

      const datasetModel = this.__getDatasetModel(locationId, datasetId);
      if (datasetModel) {
        datasetModel.getChildren().removeAll();
        if (files.length>0) {
          const locationData = osparc.data.Converters.fromDSMToVirtualTreeModel(datasetId, files);
          const datasetData = locationData[0].children;
          for (let i=0; i<datasetData[0].children.length; i++) {
            const filesModel = qx.data.marshal.Json.createModel(datasetData[0].children[i], true);
            datasetModel.getChildren().append(filesModel);
          }
        }

        this.__datasets.add(datasetId);
        this.fireEvent("filesAddedToTree");
      }

      this.__filesReceived(locationId, datasetId, files);
    },

    __filesToRoot: function(data) {
      const currentModel = this.getModel();
      osparc.file.FilesTree.removeLoadingChild(currentModel);

      const newModelToAdd = qx.data.marshal.Json.createModel(data, true);
      currentModel.getChildren().append(newModelToAdd);
      this.setModel(currentModel);
      this.fireEvent("filesAddedToTree");

      return newModelToAdd;
    },

    getSelectedFile: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        const isFile = osparc.file.FilesTree.isFile(selectedItem);
        const data = {
          selectedItem: selectedItem,
          isFile: isFile
        };
        return data;
      }
      return null;
    },

    __getFilesInTree: function(item, leaves) {
      if (item.getChildren == null) { // eslint-disable-line no-eq-null
        leaves.push(item);
      } else {
        for (let i=0; i<item.getChildren().length; i++) {
          this.__getFilesInTree(item.getChildren().toArray()[i], leaves);
        }
      }
    },

    __findUuidInLeaves: function(uuid) {
      const parent = this.getModel();
      const list = [];
      this.__getFilesInTree(parent, list);
      for (let j = 0; j < list.length; j++) {
        if (uuid === list[j].getFileId()) {
          return list[j];
        }
      }
      return null;
    },

    setSelectedFile: function(fileId) {
      const item = this.__findUuidInLeaves(fileId);
      if (item) {
        this.openNodeAndParents(item);

        const selected = new qx.data.Array([item]);
        this.setSelection(selected);
      }
    },

    __getSelectedItem: function() {
      let selection = this.getSelection().toArray();
      if (selection.length > 0) {
        return selection[0];
      }
      return null;
    },

    __selectionChanged: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        this.fireEvent("selectionChanged");
      }
    },

    __itemSelected: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        this.fireEvent("itemSelected");
      }
    },

    __addDragAndDropMechanisms: function(item) {
      if (this.getDragMechnism()) {
        this.__createDragMechanism(item);
      }

      if (this.getDropMechnism()) {
        this.__createDropMechanism(item);
      }
    },

    __createDragMechanism: function(treeItem) {
      treeItem.setDraggable(true);
      treeItem.addListener("dragstart", e => {
        if (osparc.file.FilesTree.isFile(e.getOriginalTarget())) {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-filePath");
        } else {
          e.preventDefault();
        }
      }, this);
    },

    __createDropMechanism: function(treeItem) {
      treeItem.setDroppable(true);
      treeItem.addListener("dragover", e => {
        let compatible = false;
        if (osparc.file.FilesTree.isDir(e.getOriginalTarget())) {
          if (e.supportsType("osparc-filePath")) {
            compatible = true;
          }
        }
        if (!compatible) {
          e.preventDefault();
        }
      }, this);

      treeItem.addListener("drop", e => {
        if (e.supportsType("osparc-filePath")) {
          const from = e.getRelatedTarget();
          const to = e.getCurrentTarget();
          const dataStore = osparc.store.Data.getInstance();
          console.log("Copy", from.getFileId(), "to", to.getPath());
          const requestSent = dataStore.copyFile(from.getLocation(), from.getFileId(), to.getLocation(), to.getPath());
          if (requestSent) {
            dataStore.addListenerOnce("fileCopied", ev => {
              if (ev) {
                this.fireDataEvent("fileCopied", ev.getData());
              }
            }, this);
          }
        }
      }, this);
    }
  }
});
