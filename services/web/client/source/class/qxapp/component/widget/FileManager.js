qx.Class.define("qxapp.component.widget.FileManager", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel) {
    this.base(arguments);

    this.set({
      nodeModel: nodeModel
    });

    let fileManagerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(fileManagerLayout);

    let treesLayout = this._createChildControlImpl("treesLayout");

    let nodeTree = this.__nodeTree = this._createChildControlImpl("nodeTree");
    treesLayout.add(nodeTree, {
      flex: 1
    });
    nodeTree.addListener("changeSelection", this.__itemSelected, this);

    let userTree = this.__userTree = this._createChildControlImpl("userTree");
    treesLayout.add(userTree, {
      flex: 1
    });
    userTree.addListener("changeSelection", this.__itemSelected, this);

    let selectedFileLayout = this._createChildControlImpl("selectedFileLayout");
    {
      let selectedLabel = this.__selectedLabel = new qx.ui.basic.Label().set({
        decorator: "main",
        backgroundColor: "white",
        minWidth: 300,
        height: 24
      });

      let downloadBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/cloud-download-alt/24"
      });
      downloadBtn.addListener("execute", e => {
        this.__downloadFile();
      }, this);

      let deleteBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/trash-alt/24"
      });
      deleteBtn.addListener("execute", e => {
        this.__deleteFile();
      }, this);

      selectedFileLayout.add(selectedLabel, {
        flex: 1
      });
      selectedFileLayout.add(downloadBtn);
      selectedFileLayout.add(deleteBtn);
    }

    let closeBtn = this.__closeBtn = this._createChildControlImpl("closeButton");
    closeBtn.setEnabled(false);
    closeBtn.addListener("execute", function() {
      console.log("close");
    }, this);

    this.__reloadNodeTree();
    this.__reloadUserTree();
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel"
    }
  },

  members: {
    __nodeTree: null,
    __userTree: null,
    __currentUserId: "ODEI-UUID",
    __selectedLabel: null,
    __selection: null,
    __closeBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "treesLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control, {
            flex: 1
          });
          break;
        case "nodeTree":
        case "userTree":
          control = new qx.ui.tree.Tree();
          break;
        case "selectedFileLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            alignY: "middle"
          });
          this._add(control);
          break;
        case "closeButton":
          control = new qx.ui.form.Button(this.tr("Close"));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __reloadNodeTree: function() {
      this.__nodeTree.resetRoot();

      const nodeName = this.getNodeModel().getLabel();
      let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), nodeName);
      root.setOpen(true);
      this.__nodeTree.setRoot(root);

      // this.__populateNodeFiles();
      this.__populateFiles(this.__nodeTree, true, false);
    },

    __reloadUserTree: function() {
      this.__userTree.resetRoot();

      let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), this.__currentUserId);
      root.setOpen(true);
      this.__userTree.setRoot(root);

      // this.__populateUserFiles();
      this.__populateFiles(this.__userTree, false, true);
    },

    __populateFiles: function(tree, isDraggable = false, isDroppable = false) {
      const slotName = "listObjects";
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        for (let i=0; i<data.length; i++) {
          this.__addTreeItem(data[i], tree);
        }
        let allItems = tree.getItems(true, true);
        for (let i=0; i<allItems.length; i++) {
          let treeItem = allItems[i];
          if (isDraggable && treeItem instanceof qx.ui.tree.TreeFile) {
            this.__createDragMechanism(treeItem);
          }
          if (isDroppable && treeItem instanceof qx.ui.tree.TreeFolder) {
            this.__createDropMechanism(treeItem);
          }
        }
      }, this);
      if (!socket.getSocket().connected) {
        let data = qxapp.dev.fake.Data.getObjectList();
        for (let i=0; i<data.length; i++) {
          this.__addTreeItem(data[i], tree);
        }
        let allItems = tree.getItems(true, true);
        for (let i=0; i<allItems.length; i++) {
          let treeItem = allItems[i];
          if (isDraggable && treeItem instanceof qx.ui.tree.TreeFile) {
            this.__createDragMechanism(treeItem);
          }
          if (isDroppable && treeItem instanceof qx.ui.tree.TreeFolder) {
            this.__createDropMechanism(treeItem);
          }
        }
      }
      socket.emit(slotName);
    },

    __alreadyExists: function(parentTree, itemName) {
      for (let i=0; i<parentTree.getChildren().length; i++) {
        let treeExsItem = parentTree.getChildren()[i];
        if (treeExsItem.getLabel() === itemName) {
          return treeExsItem;
        }
      }
      return null;
    },

    __addTreeItem: function(data, root) {
      let splitted = data.path.split("/");
      let parentFolder = root.getRoot();
      for (let i=0; i<splitted.length-1; i++) {
        let parentPath = splitted.slice(0, i);
        const folderName = splitted[i];
        let folderPath = {
          path: parentPath.concat(folderName).join("/")
        };
        if (this.__alreadyExists(parentFolder, folderName)) {
          parentFolder = this.__alreadyExists(parentFolder, folderName);
        } else {
          let treeItem = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), folderName, folderPath);
          parentFolder.add(treeItem);
          parentFolder = treeItem;
        }
      }

      const fileName = splitted[splitted.length-1];
      if (!this.__alreadyExists(parentFolder, fileName)) {
        let treeItem = this.__configureTreeItem(new qx.ui.tree.TreeFile(), fileName, data);
        parentFolder.add(treeItem);
      }
    },

    __configureTreeItem: function(treeItem, label, extraInfo) {
      // A left-justified icon
      treeItem.addWidget(new qx.ui.core.Spacer(16, 16));

      // Here's our indentation and tree-lines
      treeItem.addSpacer();

      if (treeItem instanceof qx.ui.tree.TreeFolder) {
        treeItem.addOpenButton();
      }

      // The standard tree icon follows
      treeItem.addIcon();

      // The label
      treeItem.addLabel(label);

      // All else should be right justified
      treeItem.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (treeItem instanceof qx.ui.tree.TreeFile) {
        // Add a file size, date and mode
        const formattedSize = qxapp.utils.Utils.formatBytes(extraInfo.size);
        let text = new qx.ui.basic.Label(formattedSize);
        text.setWidth(80);
        treeItem.addWidget(text);

        text = new qx.ui.basic.Label((new Date(extraInfo.lastModified)).toUTCString());
        text.setMinWidth(200);
        treeItem.addWidget(text);

        treeItem.addListener("click", function(mouseEvent) {
          this.__itemSelected();
        }, this);
      }

      if (extraInfo) {
        treeItem.path = extraInfo.path;
      }

      if (treeItem instanceof qx.ui.tree.TreeFile) {
        treeItem.isDir = false;
      } else if (treeItem instanceof qx.ui.tree.TreeFolder) {
        treeItem.isDir = true;
      }

      return treeItem;
    },

    __createDragMechanism: function(treeItem) {
      treeItem.setDraggable(true);
      treeItem.addListener("dragstart", e => {
        if (e.getOriginalTarget().isDir == true) {
          e.preventDefault();
        } else {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-filePath");
        }
      }, this);
    },

    __createDropMechanism: function(treeItem) {
      treeItem.setDroppable(true);
      treeItem.addListener("dragover", e => {
        let compatible = false;
        if (e.supportsType("osparc-filePath")) {
          const from = e.getRelatedTarget();
          const to = e.getCurrentTarget();
          if (from.isDir === false && to.isDir === true) {
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
          console.log("Copy", from.path, "to", to.path);
        }
      }, this);
    },

    __itemSelected: function() {
      let selectedItem = this.__nodeTree.getSelection();
      if (selectedItem.length < 1) {
        return;
      }
      if ("path" in selectedItem[0]) {
        const data = {
          itemPath: selectedItem[0].path,
          isDirectory: selectedItem[0].isDir
        };
        this.__selection = data.itemPath;
        this.__selectedLabel.setValue(data.itemPath);
      }
    },

    __downloadFile: function() {
      console.log("Download ", this.__selection);
    },

    __deleteFile: function() {
      console.log("Delete ", this.__selection);
    }
  }
});
