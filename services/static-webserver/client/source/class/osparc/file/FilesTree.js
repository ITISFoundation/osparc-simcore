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
 * "osparc-file-link" type is used for the Drag&Drop.
 *
 *   If a file is dropped into a folder, this class will start the copying process firing
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
      decorator: "no-border",
      font: "text-14",
    });

    this.__resetChecks();

    this.addListener("tap", this.__selectionChanged, this);

    // Listen to "Enter" key
    this.addListener("keypress", keyEvent => {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);

    this.__pathModels = [];
    this.__loadPaths = {};
  },

  properties: {
    dragMechanism: {
      check: "Boolean",
      init: false
    },

    dropMechanism: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Event", // tap
    "itemSelected": "qx.event.type.Event", // dbltap
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
      const loadingModel = qx.data.marshal.Json.createModel({
        label: "Loading...",
        location: null,
        path: null,
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12"
      }, true);
      parent.getChildren().append(loadingModel);
    },

    removeLoadingChild: function(parent) {
      for (let i = parent.getChildren().length - 1; i >= 0; i--) {
        if (parent.getChildren().toArray()[i].getLabel() === "Loading...") {
          parent.getChildren().toArray()
            .splice(i, 1);
        }
      }
    },

    attachPathLabel: function(srcPathLabel, data) {
      data["pathLabel"] = srcPathLabel.concat(data["label"]);
      if ("children" in data) {
        data.children.forEach(child => this.self().attachPathLabel(data["pathLabel"], child));
      }
    }
  },

  members: {
    __locations: null,
    __pathModels: null,
    __loadPaths: null,

    resetCache: function() {
      this.__resetChecks();

      const dataStore = osparc.store.Data.getInstance();
      dataStore.resetCache();
    },

    populateLocations: function() {
      this.__resetChecks();

      const treeName = "My Data";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      rootModel.getChildren().removeAll();
      this.self().addLoadingChild(rootModel);

      this.set({
        hideRoot: true
      });
      const dataStore = osparc.store.Data.getInstance();
      return dataStore.getLocations()
        .then(locations => {
          const datasetPromises = [];
          if (this.__locations.size === 0) {
            this.__resetChecks();
            this.__locationsToRoot(locations);
            for (let i=0; i<locations.length; i++) {
              const locationId = locations[i]["id"];
              datasetPromises.push(this.__populateLocation(locationId));
            }
          }
          return datasetPromises;
        });
    },

    populateStudyTree: function(studyId) {
      const treeName = osparc.product.Utils.getStudyAlias({firstUpperCase: true}) + " Files";
      this.__resetTree(treeName);
      const studyModel = this.getModel();
      this.self().addLoadingChild(studyModel);

      const dataStore = osparc.store.Data.getInstance();
      const locationId = 0;
      const path = studyId;
      return dataStore.getItemsByLocationAndPath(locationId, path)
        .then(items => {
          if (items.length) {
            const studyName = items[0]["display_path"].split("/")[0];
            studyModel.setLabel(studyName);
          }
          this.__itemsToTree(locationId, path, items, studyModel);

          // select study item
          this.setSelection(new qx.data.Array([studyModel]));
          this.__selectionChanged();
        });
    },

    populateNodeTree(nodeId) {
      const treeName = "Node Files";
      this.__resetTree(treeName);
      const rootModel = this.getModel();
      this.self().addLoadingChild(rootModel);

      const dataStore = osparc.store.Data.getInstance();
      return dataStore.getNodeFiles(nodeId)
        .then(files => {
          const newChildren = osparc.data.Converters.fromDSMToVirtualTreeModel(0, null, files);
          if (newChildren.length && // location
            newChildren[0].children.length && // study
            newChildren[0].children[0].children.length) { // node
            const nodeData = newChildren[0].children[0].children[0];
            const nodeTreeName = nodeData.label;
            this.__resetTree(nodeTreeName, nodeId);
            const rootNodeModel = this.getModel();
            if (nodeData.children.length) {
              const nodeItemsOnly = nodeData.children;
              this.__itemsToNode(nodeItemsOnly);
            }
            this.openNode(rootNodeModel);

            // select node item
            this.setSelection(new qx.data.Array([rootNodeModel]));
            this.__selectionChanged();
          } else {
            rootModel.getChildren().removeAll();
          }
        });
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

      this.populateLocations();
    },

    requestPathItems: function(locationId, path) {
      const dataStore = osparc.store.Data.getInstance();
      dataStore.getItemsByLocationAndPath(locationId, path)
        .then(items => {
          this.__itemsToTree(locationId, path, items);
        });
    },

    __resetChecks: function() {
      this.__locations = new Set();
    },

    __resetTree: function(treeName, itemId) {
      itemId = itemId || treeName.replace(/\s/g, ""); // default to tree name without white spaces
      this.resetModel();
      const rootData = {
        label: treeName,
        itemId,
        location: null,
        path: null,
        pathLabel: [treeName],
        children: []
      };
      const root = qx.data.marshal.Json.createModel(rootData, true);

      this.setModel(root);
      this.setDelegate({
        createItem: () => new osparc.file.FileTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("itemId", "itemId", null, item, id);
          c.bindProperty("displayPath", "displayPath", null, item, id);
          c.bindProperty("fileId", "fileId", null, item, id);
          c.bindProperty("location", "location", null, item, id);
          c.bindProperty("datasetId", "datasetId", null, item, id);
          c.bindProperty("loaded", "loaded", null, item, id);
          c.bindProperty("path", "path", null, item, id);
          c.bindProperty("pathLabel", "pathLabel", null, item, id);
          c.bindProperty("lastModified", "lastModified", null, item, id);
          c.bindProperty("size", "size", null, item, id);
          c.bindProperty("icon", "icon", null, item, id);
        },
        configureItem: item => {
          const openButton = item.getChildControl("open");
          openButton.addListener("tap", () => {
            if (item.isOpen() && !item.getLoaded()) {
              item.setLoaded(true);
              const locationId = item.getLocation();
              const path = item.getPath();
              this.requestPathItems(locationId, path);
            }
          }, this);
          item.addListener("dbltap", () => this.__itemSelected(), this);
          this.__addDragAndDropMechanisms(item);
        }
      });
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
        locationData["pathLabel"] = rootModel.getPathLabel().concat(locationData["label"]);
        const locationModel = this.__createModel(location.id, null, locationData);
        rootModel.getChildren().append(locationModel);
        if (this.__hasLocationNeedToBeLoaded(location.id)) {
          openThis = locationModel;
        }
      }
      if (openThis) {
        this.openNodeAndParents(openThis);
      }
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

    __populateLocation: function(locationId = null) {
      if (locationId !== null) {
        const locationModel = this.__getLocationModel(locationId);
        if (locationModel) {
          locationModel.getChildren().removeAll();
          this.self().addLoadingChild(locationModel);
        }
      }

      const dataStore = osparc.store.Data.getInstance();
      return dataStore.getDatasetsByLocation(locationId)
        .then(data => {
          const {
            location,
            items,
          } = data;
          if (location === locationId && !this.__locations.has(locationId)) {
            this.__itemsToLocation(location, items);
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

    __getModelFromPath: function(locationId, path) {
      const modelFound = this.__pathModels.find(entry => entry["locationId"] == locationId && entry["path"] === path);
      if (modelFound) {
        return modelFound["model"];
      }
      return null;
    },

    __createModel: function(locationId, path, data) {
      const model = qx.data.marshal.Json.createModel(data, true);
      this.__pathModels.push({
        locationId,
        path,
        model,
      });
      return model;
    },

    __itemsToTree: function(locationId, path, items, parentModel) {
      if (!parentModel) {
        parentModel = this.__getModelFromPath(locationId, path);
      }
      if (parentModel) {
        parentModel.getChildren().removeAll();
        items.forEach(item => {
          if (item["file_meta_data"]) {
            const data = osparc.data.Converters.createFileEntry(
              item["display_path"],
              locationId,
              item["path"],
              item["file_meta_data"],
            );
            const model = this.__createModel(locationId, item["path"], data);
            parentModel.getChildren().append(model);
          } else {
            const data = osparc.data.Converters.createDirEntry(
              item["display_path"],
              locationId,
              item["path"]
            );
            data.loaded = false;
            const model = this.__createModel(locationId, item["path"], data);
            parentModel.getChildren().append(model);
            this.__pathModels.push({
              locationId,
              path: item["path"],
              model,
            });
            this.self().addLoadingChild(model);
          }
        });
        // sort files
        osparc.data.Converters.sortModelByLabel(parentModel);

        this.__rerender(parentModel);

        this.fireEvent("filesAddedToTree");
      }

      this.__filesReceived(locationId, path, items);
    },

    __itemsToNode: function(files) {
      const currentModel = this.getModel();
      this.self().removeLoadingChild(currentModel);

      files.forEach(file => this.self().attachPathLabel(currentModel.getPathLabel(), file));
      const newModelToAdd = qx.data.marshal.Json.createModel(files, true);
      currentModel.getChildren().append(newModelToAdd);
      this.setModel(currentModel);
      this.fireEvent("filesAddedToTree");

      return newModelToAdd;
    },

    __itemsToLocation: function(locationId, items) {
      const locationModel = this.__getLocationModel(locationId);
      if (!locationModel) {
        return;
      }
      this.__locations.add(locationId);
      locationModel.getChildren().removeAll();
      let openThis = null;
      items.forEach(item => {
        const datasetData = osparc.data.Converters.createDirEntry(
          item["display_path"],
          locationId,
          item["path"]
        );
        datasetData.loaded = false;
        datasetData["pathLabel"] = locationModel.getPathLabel().concat(datasetData["label"]);
        const datasetModel = this.__createModel(locationId, item["path"], datasetData);
        this.self().addLoadingChild(datasetModel);
        locationModel.getChildren().append(datasetModel);

        // add cached files
        const path = item["path"];
        if (this.__hasDatasetNeedToBeLoaded(locationId, path)) {
          openThis = datasetModel;
        }
      });
      // sort datasets
      osparc.data.Converters.sortModelByLabel(locationModel);

      this.__rerender(locationModel);

      if (openThis) {
        const path = openThis.getItemId();
        this.openNodeAndParents(openThis);
        this.requestPathItems(locationId, path);
      }
    },

    __itemsToDataset: function(locationId, datasetId, files, model) {
      const datasetModel = model ? model : this.__getModelFromPath(locationId, datasetId);
      if (datasetModel) {
        datasetModel.getChildren().removeAll();
        if (files.length) {
          // OM here
          const locationData = osparc.data.Converters.fromDSMToVirtualTreeModel(locationId, datasetId, files);
          const datasetData = locationData[0].children;
          datasetData[0].children.forEach(data => {
            this.self().attachPathLabel(datasetModel.getPathLabel(), data);
            const filesModel = qx.data.marshal.Json.createModel(data, true);
            datasetModel.getChildren().append(filesModel);
          });
        }
        // sort files
        osparc.data.Converters.sortModelByLabel(datasetModel);

        this.__rerender(datasetModel);

        this.fireEvent("filesAddedToTree");
      }

      this.__filesReceived(locationId, datasetId, files);
    },

    __rerender: function(item) {
      // Hack to trigger a rebuild of the item.
      // Without this sometimes the arrow giving access to the children is not rendered
      if (!this.isNodeOpen(item)) {
        this.openNode(item);
        this.closeNode(item);
      }
    },

    getParent: function(childItem) {
      const root = this.getModel();
      const list = [];
      this.__getItemsInTree(root, list);
      return list.find(element => element.getChildren && element.getChildren().contains(childItem));
    },

    findItemId: function(itemId) {
      const root = this.getModel();
      const items = [];
      this.__getItemsInTree(root, items);
      return items.find(element => "getItemId" in element && element.getItemId() === itemId);
    },

    __getItemsInTree: function(item, items) {
      items.push(item);
      if (item.getChildren) {
        item.getChildren().forEach(child => {
          this.__getItemsInTree(child, items);
        });
      }
    },

    __getLeavesInTree: function(item, leaves) {
      if (item.getChildren == null) {
        leaves.push(item);
      } else {
        item.getChildren().forEach(child => {
          this.__getLeavesInTree(child, leaves);
        });
      }
    },

    __findUuidInLeaves: function(uuid) {
      const root = this.getModel();
      const leaves = [];
      this.__getLeavesInTree(root, leaves);
      return leaves.find(element => element.getFileId() === uuid);
    },

    setSelectedFile: function(fileId) {
      const item = this.__findUuidInLeaves(fileId);
      if (item) {
        this.openNodeAndParents(item);

        const selectItem = new qx.data.Array();
        if (this.getShowLeafs()) {
          selectItem.push(item);
        } else {
          console.log("select parent", fileId);
          const parent = this.getParent(item);
          if (parent) {
            selectItem.push(parent);
          }
        }
        if (selectItem.length) {
          this.setSelection(selectItem);
          this.__selectionChanged();
          return true;
        }
      }

      return false;
    },

    getSelectedItem: function() {
      let selection = this.getSelection().toArray();
      if (selection.length > 0) {
        return selection[0];
      }
      return null;
    },

    __selectionChanged: function() {
      let selectedItem = this.getSelectedItem();
      if (selectedItem) {
        this.fireEvent("selectionChanged");
      }
    },

    __itemSelected: function() {
      let selectedItem = this.getSelectedItem();
      if (selectedItem) {
        this.fireEvent("itemSelected");
      }
    },

    __addDragAndDropMechanisms: function(item) {
      if (this.isDragMechanism()) {
        this.__createDragMechanism(item);
      }

      if (this.isDropMechanism()) {
        this.__createDropMechanism(item);
      }
    },

    __createDragMechanism: function(treeItem) {
      treeItem.setDraggable(true);
      treeItem.addListener("dragstart", e => {
        const origin = e.getOriginalTarget();
        if (this.self().isFile(origin)) {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-file-link");

          e.addData("osparc-file-link", {
            dragData: origin.getModel()
          });
        } else {
          e.preventDefault();
        }
      }, this);
    },

    __createDropMechanism: function(treeItem) {
      treeItem.setDroppable(true);
      treeItem.addListener("dragover", e => {
        let compatible = false;
        if (this.self().isDir(e.getOriginalTarget())) {
          if (e.supportsType("osparc-file-link")) {
            compatible = true;
          }
        }
        if (!compatible) {
          e.preventDefault();
        }
      }, this);

      treeItem.addListener("drop", e => {
        if (e.supportsType("osparc-file-link")) {
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
