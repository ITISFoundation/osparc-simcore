/* global XMLHttpRequest */
qx.Class.define("qxapp.component.widget.FilePicker", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    // Create a button
    let input = new qx.html.Input("file", {
      display: "none"
    }, {
      multiple: true,
      accept: "image/*"
    });

    this.getContentElement().add(input);

    let pick = this._createChildControlImpl("addButton");
    // Add an event listener
    pick.addListener("execute", e => {
      input.getDomElement().click();
    });

    input.addListener("change", e => {
      let files = input.getDomElement().files;
      for (let i=0; i<files.length; i++) {
        this.__retrieveURLAndUpload(files[i]);
      }
    }, this);

    let tree = this.__mainTree = this._createChildControlImpl("treeMenu");
    tree.addListener("changeSelection", this.__selectionChanged, this);

    let selectBtn = this.__selectBtn = this._createChildControlImpl("selectButton");
    selectBtn.setEnabled(false);
    selectBtn.addListener("execute", function() {
      this.__itemSelected();
    }, this);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);

    this.__reloadTree();

    this.__createConnections(node);
  },

  events: {
    "ItemSelected": "qx.event.type.Data",
    "Finished": "qx.event.type.Event"
  },

  members: {
    __mainTree: null,
    __selectBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "addButton":
          control = new qx.ui.form.Button(this.tr("Add file(s)"));
          this._add(control);
          break;
        case "treeMenu":
          control = new qx.ui.tree.Tree();
          this._add(control, {
            flex: 1
          });
          break;
        case "selectButton":
          control = new qx.ui.form.Button(this.tr("Select"));
          this._add(control);
          break;
        case "progressBox":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 1);
          break;
      }

      return control || this.base(arguments, id);
    },

    __reloadTree: function() {
      this.__mainTree.resetRoot();

      let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), this.tr("Available Files"));
      root.setOpen(true);
      this.__mainTree.setRoot(root);

      this.__getObjLists();
    },

    __createConnections: function(node) {
      this.addListener("ItemSelected", function(data) {
        const itemPath = data.getData().itemPath;
        let outputs = node.getOutputs();
        outputs["outFile"].value = {
          store: "s3-z43",
          path: itemPath
        };
        // node.setProgress(100);
        this.fireEvent("Finished");
      }, this);
    },

    __getObjLists: function() {
      const slotName = "listObjects";
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        console.log(slotName, data);
        for (let i=0; i<data.length; i++) {
          this.__addTreeItem(data[i]);
        }
      }, this);
      if (!socket.getSocket().connected) {
        let data = qxapp.dev.fake.Data.getObjectList();
        for (let i=0; i<data.length; i++) {
          this.__addTreeItem(data[i]);
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

    __addTreeItem: function(data) {
      let splitted = data.path.split("/");
      let parentFolder = this.__mainTree.getRoot();
      for (let i=0; i<splitted.length-1; i++) {
        let parentPath = splitted.slice(0, i);
        const folderName = splitted[i];
        let folderPath = {
          path: parentPath.concat(folderName).join("/")
        };
        if (this.__alreadyExists(parentFolder, folderName)) {
          parentFolder = this.__alreadyExists(parentFolder, folderName);
        } else {
          let newFolder = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), folderName, folderPath);
          parentFolder.add(newFolder);
          parentFolder = newFolder;
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
        text.setWidth(200);
        treeItem.addWidget(text);

        // Listen to "Double Click" key
        treeItem.addListener("dblclick", function(mouseEvent) {
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

    // Request to the server an upload URL.
    __retrieveURLAndUpload: function(file) {
      let socket = qxapp.wrappers.WebSocket.getInstance();

      const slotName = "presignedUrl";
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        const url = data["url"];
        this.__uploadFile(file, url);
      }, this);
      const data = {
        bucketName: qxapp.dev.fake.Data.getS3PublicBucketName(),
        fileName: file.name
      };
      socket.emit(slotName, data);
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: function(file, url) {
      let hBox = this._createChildControlImpl("progressBox");
      let label = new qx.ui.basic.Label(file.name);
      let progressBar = new qx.ui.indicator.ProgressBar();
      hBox.add(label, {
        width: "15%"
      });
      hBox.add(progressBar, {
        width: "85%"
      });
      let xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", e => {
        if (e.lengthComputable) {
          const percentComplete = e.loaded / e.total * 100;
          progressBar.setValue(percentComplete);
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      xhr.open("PUT", url, true);
      xhr.send(file);
      xhr.onload = () => {
        if (xhr.status == 200) {
          console.log("Uploaded", file.name);
          hBox.destroy();
          this.__reloadTree();
        }
      };
    },

    __selectionChanged: function() {
      let selectedItem = this.__mainTree.getSelection();
      this.__selectBtn.setEnabled("path" in selectedItem[0]);
    },

    __itemSelected: function() {
      let selectedItem = this.__mainTree.getSelection();
      if ("path" in selectedItem[0]) {
        const data = {
          itemPath: selectedItem[0].path,
          isDirectory: selectedItem[0].isDir
        };
        this.fireDataEvent("ItemSelected", data);
      }
    }
  }
});
