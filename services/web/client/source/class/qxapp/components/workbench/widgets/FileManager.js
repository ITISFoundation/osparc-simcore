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

    let pick = new qx.ui.form.Button("Upload");
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


    let tree = new qx.ui.tree.Tree();
    this.add(tree, {
      flex: 1
    });

    let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Available Files");
    root.setOpen(true);
    tree.setRoot(root);

    let tree1 = this.__publicTree = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Public Files");
    root.add(tree1);

    let tree2 = this.__userTree = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "User Files");
    root.add(tree2);

    this.__reloadTree();
  },

  members: {
    __publicTree: null,
    __userTree: null,

    // Request to the server an upload URL.
    __retrieveURLAndUpload: function(file) {
      let socket = qxapp.wrappers.WebSocket.getInstance();
      if (!socket.slotExists("presignedUrl")) {
        socket.on("presignedUrl", function(data) {
          console.log("presignedUrl", data);
          const url = data["url"];
          this.__uploadFile(file, url);
        }, this);
      }
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
        }
      };
    },

    __reloadTree: function() {
      this.__publicTree.removeAll();
      this.__userTree.removeAll();

      this.__getObjLists("maiz");
    },

    __getObjLists: function(bucketName) {
      let socket = qxapp.wrappers.WebSocket.getInstance();
      if (!socket.slotExists("listObjectsPub")) {
        socket.on("listObjectsPub", function(data) {
          console.log("listObjectsPub", data);
          this.__addTreeItem(data);
        }, this);
      }
      if (!socket.slotExists("listObjectsUser")) {
        socket.on("listObjectsUser", function(data) {
          console.log("listObjectsUser", data);
          this.__addTreeItem(data);
        }, this);
      }
      socket.emit("listObjects", bucketName);
    },

    __addTreeItem: function(data) {
      let treeItem = this.__configureTreeItem(new qx.ui.tree.TreeFile(), data.data.name, data.data);
      if (data.owner === "user") {
        this.__userTree.add(treeItem);
      } else if (data.owner === "public") {
        this.__publicTree.add(treeItem);
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

        text = new qx.ui.basic.Label(extraInfo.lastModified);
        text.setWidth(200);
        treeItem.addWidget(text);

        text = new qx.ui.basic.Label("-rw-r--r--");
        text.setWidth(100);
        treeItem.addWidget(text);
      }

      return treeItem;
    }
  }
});
