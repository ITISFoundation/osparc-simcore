/* global XMLHttpRequest */
qx.Class.define("qxapp.components.workbench.widgets.FileManager", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base();

    this.set({
      showMinimize: false,
      showStatusbar: false,
      width: 800,
      height: 600,
      minWidth: 400,
      minHeight: 400,
      modal: true,
      caption: "File Manager"
    });

    let fileManagerLayout = new qx.ui.layout.VBox(10);
    this.setLayout(fileManagerLayout);


    // Create a button
    let input = new qx.html.Input("file", {
      display: "none"
    }, {
      multiple: true,
      accept: "image/*"
    });

    this.getContentElement().add(input);

    let pick = new qx.ui.form.Button(this.tr("Add file(s)"));
    this.add(pick);

    // Add an event listener
    pick.addListener("execute", function(e) {
      input.getDomElement().click();
    });

    input.addListener("change", function(e) {
      let files = input.getDomElement().files;
      for (let i=0; i<files.length; i++) {
        this.__retrieveURLAndUpload(files[i]);
      }
    }, this);

    let tree = this.__mainTree = new qx.ui.tree.Tree();
    this.add(tree, {
      flex: 1
    });
    tree.addListener("changeSelection", this.__selectionChanged, this);

    this.__selectBtn = new qx.ui.form.Button(this.tr("Select"));
    this.__selectBtn.setEnabled(false);
    this.add(this.__selectBtn);
    this.__selectBtn.addListener("execute", function() {
      this.__itemSelected();
    }, this);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);

    this.__reloadTree();
  },

  events: {
    "FileSelected": "qx.event.type.Data",
    "FolderSelected": "qx.event.type.Data"
  },

  members: {
    __mainTree: null,
    __selectBtn: null,

    __reloadTree: function() {
      this.__mainTree.resetRoot();

      let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), this.tr("Available Files"));
      root.setOpen(true);
      this.__mainTree.setRoot(root);

      this.__getObjLists();
    },

    __getObjLists: function() {
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot("listObjects");
      socket.on("listObjects", function(data) {
        console.log("listObjects", data);
        for (let i=0; i<data.length; i++) {
          this.__addTreeItem(data[i]);
        }
      }, this);
      socket.emit("listObjects");
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

      socket.removeSlot("presignedUrl");
      socket.on("presignedUrl", function(data) {
        const url = data["url"];
        this.__uploadFile(file, url);
      }, this);
      const data = {
        bucketName: qxapp.qxapp.dev.fake.Data.getS3PublicBucketName(),
        fileName: file.name
      };
      socket.emit("presignedUrl", data);
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: function(file, url) {
      let hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      let label = new qx.ui.basic.Label(file.name);
      let progressBar = new qx.ui.indicator.ProgressBar();
      hBox.add(label, {
        width: "15%"
      });
      hBox.add(progressBar, {
        width: "85%"
      });
      this.addAt(hBox, 1);
      let xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", function(e) {
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
          this.remove(hBox);
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
          filePath: selectedItem[0].path
        };
        if (selectedItem[0].isDir) {
          this.fireDataEvent("FolderSelected", data);
        } else {
          this.fireDataEvent("FileSelected", data);
        }
      }
    }
  }
});
