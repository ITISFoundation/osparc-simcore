/* global XMLHttpRequest */
qx.Class.define("qxapp.components.workbench.widgets.FileManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.VBox(10));


    // Create a button
    let input = new qx.html.Input("file", {
      display: "none"
    }, {
      multiple: true,
      accept: "image/*"
    });

    this.getContentElement().add(input);

    let pick = new qx.ui.form.Button("Add file");
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

    this.__selectFileBtn = new qx.ui.form.Button("Select File");
    this.__selectFileBtn.setEnabled(false);
    this.add(this.__selectFileBtn);
    this.__selectFileBtn.addListener("execute", function() {
      this.__fileSelected();
    }, this);

    this.__reloadTree();
  },

  events: {
    "FileSelected": "qx.event.type.Data"
  },

  members: {
    __mainTree: null,
    __publicTree: null,
    __userTree: null,
    __selectFileBtn: null,

    __reloadTree: function() {
      this.__mainTree.resetRoot();

      let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Available Files");
      root.setOpen(true);
      this.__mainTree.setRoot(root);

      let tree1 = this.__publicTree = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Public Files");
      tree1.setOpen(true);
      root.add(tree1);

      let tree2 = this.__userTree = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "User Files");
      tree2.setOpen(true);
      root.add(tree2);

      this.__getObjLists("maiz");
    },

    __getObjLists: function(bucketName) {
      let socket = qxapp.wrappers.WebSocket.getInstance();

      socket.removeSlot("listObjectsPub");
      socket.on("listObjectsPub", function(data) {
        let treeItem = this.__addTreeItem(this.__publicTree, data);
        treeItem.path = "simcore/" + data.name;
      }, this);

      socket.removeSlot("listObjectsUser");
      socket.on("listObjectsUser", function(data) {
        let treeItem = this.__addTreeItem(this.__userTree, data);
        treeItem.path = "maiz/" + data.name;
      }, this);

      socket.emit("listObjects", bucketName);
    },

    // Request to the server an upload URL.
    __retrieveURLAndUpload: function(file) {
      let socket = qxapp.wrappers.WebSocket.getInstance();

      socket.removeSlot("presignedUrl");
      socket.on("presignedUrl", function(data) {
        const url = data["url"];
        this.__uploadFile(file, url);
      }, this);
      socket.emit("presignedUrl", file.name);
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: function(file, url) {
      let xhr = new XMLHttpRequest();
      xhr.addEventListener("progress", function(oEvent) {
        if (oEvent.lengthComputable) {
          const percentComplete = oEvent.loaded / oEvent.total * 100;
          console.log(percentComplete);
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      });
      xhr.open("PUT", url, true);
      xhr.send(file);
      xhr.onload = () => {
        if (xhr.status == 200) {
          console.log("Uploaded", file.name);
          this.__reloadTree();
        }
      };
    },

    __selectionChanged: function() {
      let selectedItem = this.__mainTree.getSelection();
      this.__selectFileBtn.setEnabled("path" in selectedItem[0]);
    },

    __fileSelected: function() {
      let selectedItem = this.__mainTree.getSelection();
      if ("path" in selectedItem[0]) {
        const data = {
          filePath: selectedItem[0].path
        };
        this.fireDataEvent("FileSelected", data);

        console.log();
      }
    },

    __addTreeItem: function(tree, data) {
      let treeItem = this.__configureTreeItem(new qx.ui.tree.TreeFile(), data.name, data);
      tree.add(treeItem);

      return treeItem;
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
      }

      return treeItem;
    }
  }
});
