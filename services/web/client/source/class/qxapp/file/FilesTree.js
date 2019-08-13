/* ************************************************************************

   qxapp - the simcore frontend

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
 *   let filesTree = new qxapp.file.FilesTree();
 *   this.getRoot().add(filesTree);
 * </pre>
 */

qx.Class.define("qxapp.file.FilesTree", {
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
      const loadingModel = new qxapp.file.FileTreeItem().set({
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

    resetChecks: function() {
      this.__locations = new Set();
      this.__datasets = new Set();
    },

    resetCache: function() {
      this.resetChecks();

      const filesStore = qxapp.store.Data.getInstance();
      filesStore.resetCache();
    },

    populateTree: function(nodeId = null, locationId = null) {
      if (nodeId) {
        this.__populateNodeFiles(nodeId);
      } else if (locationId) {
        this.__populateMyLocation(locationId);
      } else {
        this.__populateMyData();
      }

      this.getDelegate().configureItem = item => {
        item.addListener("dbltap", e => {
          this.__itemSelected();
        }, this);
        this.__addDragAndDropMechanisms(item);
      };
    },

    __populateNodeFiles: function(nodeId) {
      const treeName = "Node files";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      qxapp.file.FilesTree.addLoadingChild(rootModel);

      const filesStore = qxapp.store.Data.getInstance();
      filesStore.addListenerOnce("nodeFiles", e => {
        const files = e.getData();
        const newChildren = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
        this.__filesToRoot(newChildren);
      }, this);
      filesStore.getNodeFiles(nodeId);
    },

    __populateMyData: function() {
      this.resetChecks();

      const treeName = "My Data";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      rootModel.getChildren().removeAll();
      qxapp.file.FilesTree.addLoadingChild(rootModel);

      const filesStore = qxapp.store.Data.getInstance();
      filesStore.addListenerOnce("myLocations", e => {
        const locations = e.getData();
        if (this.__locations.size === 0) {
          this.resetChecks();

          this.__locationsToRoot(locations);

          for (let i=0; i<locations.length; i++) {
            const locationId = locations[i]["id"];
            this.__populateMyLocation(locationId);
          }
        }
      }, this);
      filesStore.getLocations();
    },

    __populateMyLocation: function(locationId = null) {
      if (locationId !== null) {
        const locationModel = this.__getLocationModel(locationId);
        if (locationModel) {
          locationModel.getChildren().removeAll();
          qxapp.file.FilesTree.addLoadingChild(locationModel);
        }
      }

      const filesStore = qxapp.store.Data.getInstance();
      filesStore.addListener("myDatasets", ev => {
        const {
          location,
          datasets
        } = ev.getData();
        if (location === locationId && !this.__locations.has(locationId)) {
          this.__datasetsToLocation(location, datasets);
        }
      }, this);
      filesStore.getDatasetsByLocation(locationId);
    },

    __resetTree: function(treeName) {
      // FIXME: It is not reseting the model
      this.resetModel();
      const rootData = {
        label: treeName,
        location: null,
        path: null,
        children: []
      };
      const root = qx.data.marshal.Json.createModel(rootData, true);

      this.setModel(root);
      this.setDelegate({
        createItem: () => {
          const fileTreeItem = new qxapp.file.FileTreeItem();
          fileTreeItem.addListener("requestFiles", e => {
            const {
              locationId,
              datasetId
            } = e.getData();

            if (this.__datasets.has(datasetId)) {
              return;
            }

            const filesStore = qxapp.store.Data.getInstance();
            filesStore.addListener("myDocuments", ev => {
              const {
                location,
                dataset,
                files
              } = ev.getData();
              this.__filesToDataset(location, dataset, files);
            }, this);
            filesStore.getFilesByLocationAndDataset(locationId, datasetId);
          }, this);
          return fileTreeItem;
        },
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("fileId", "fileId", null, item, id);
          c.bindProperty("location", "location", null, item, id);
          c.bindProperty("isDataset", "isDataset", null, item, id);
          c.bindProperty("loaded", "loaded", null, item, id);
          c.bindProperty("path", "path", null, item, id);
          c.bindProperty("lastModified", "lastModified", null, item, id);
          c.bindProperty("size", "size", null, item, id);
          c.bindProperty("icon", "icon", null, item, id);
        }
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

    __datasetsToLocation: function(locationId, datasets) {
      const filesStore = qxapp.store.Data.getInstance();

      const locationModel = this.__getLocationModel(locationId);
      if (!locationModel) {
        return;
      }
      this.__locations.add(locationId);
      locationModel.getChildren().removeAll();
      for (let i=0; i<datasets.length; i++) {
        const dataset = datasets[i];
        const datasetData = qxapp.data.Converters.createDirEntry(
          dataset.display_name,
          locationId,
          dataset.dataset_id,
        );
        datasetData.isDataset = true;
        datasetData.loaded = false;
        const datasetModel = qx.data.marshal.Json.createModel(datasetData, true);
        qxapp.file.FilesTree.addLoadingChild(datasetModel);
        locationModel.getChildren().append(datasetModel);

        // add cached files
        const datasetId = dataset.dataset_id;
        const cachedData = filesStore.getFilesByLocationAndDatasetCached(locationId, datasetId);
        if (cachedData) {
          this.__filesToDataset(cachedData.location, cachedData.dataset, cachedData.files);
        }
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
          const locationData = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
          const datasetData = locationData[0].children;
          for (let i=0; i<datasetData[0].children.length; i++) {
            const filesModel = qx.data.marshal.Json.createModel(datasetData[0].children[i], true);
            datasetModel.getChildren().append(filesModel);
          }
        }

        this.__datasets.add(datasetId);
        this.fireEvent("filesAddedToTree");
      }
    },

    __filesToRoot: function(data) {
      const currentModel = this.getModel();
      qxapp.file.FilesTree.removeLoadingChild(currentModel);

      const newModelToAdd = qx.data.marshal.Json.createModel(data, true);
      currentModel.getChildren().append(newModelToAdd);
      this.setModel(currentModel);
      this.fireEvent("filesAddedToTree");
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
    },

    getSelectedFile: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        const isFile = qxapp.file.FilesTree.isFile(selectedItem);
        const data = {
          selectedItem: selectedItem,
          isFile: isFile
        };
        return data;
      }
      return null;
    },

    addFileEntry: function(fileMetadata) {
      console.log("file copied", fileMetadata);
    },

    __getLeafList: function(item, leaves) {
      if (item.getChildren == null) { // eslint-disable-line no-eq-null
        leaves.push(item);
      } else {
        for (let i=0; i<item.getChildren().length; i++) {
          this.__getLeafList(item.getChildren().toArray()[i], leaves);
        }
      }
    },

    __findUuidInLeaves: function(uuid) {
      const parent = this.getModel();
      const list = [];
      this.__getLeafList(parent, list);
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
        if (qxapp.file.FilesTree.isFile(e.getOriginalTarget())) {
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
        if (qxapp.file.FilesTree.isDir(e.getOriginalTarget())) {
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
          const dataStore = qxapp.store.Data.getInstance();
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
