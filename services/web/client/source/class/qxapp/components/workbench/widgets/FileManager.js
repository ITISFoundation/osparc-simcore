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

    let root = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Available Files", null, false);
    root.setOpen(true);
    tree.setRoot(root);
    // tree.setHideRoot(true);

    let tree1 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Public Files");
    root.add(tree1);
    this.__getFilesTree(tree1);

    let tree2 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "User Files");
    root.add(tree2);
    this.__getFilesTree(tree2);
  },

  members: {
    __minio: null,
    __minioPubClient: null,

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

    __getFilesTree: function(treeRoot) {
      let tree11 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Files");
      let tree12 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Workspace");
      let tree13 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Network");
      let tree14 = this.__configureTreeItem(new qx.ui.tree.TreeFolder(), "Trash");
      treeRoot.add(tree11, tree12, tree13, tree14);

      // One icon specified, and used for both selected unselected states
      let tree121 = this.__configureTreeItem(new qx.ui.tree.TreeFile(), "Windows (C:)", "icon/16/devices/drive-harddisk.png");
      let tree122 = this.__configureTreeItem(new qx.ui.tree.TreeFile(), "Documents (D:)", "icon/16/devices/drive-harddisk.png");
      tree12.add(tree121, tree122);
    },

    __configureTreeItem: function(treeItem, vLabel, vIcon, extraInfo = true) {
      // A left-justified icon
      /*
      if (Math.floor(Math.random() * 4) == 0) {
        let img = new qx.ui.basic.Image("icon/16/status/dialog-information.png");
        treeItem.addWidget(img);
      } else {
        treeItem.addWidget(new qx.ui.core.Spacer(16, 16));
      }
      */
      treeItem.addWidget(new qx.ui.core.Spacer(16, 16));

      // Here's our indentation and tree-lines
      treeItem.addSpacer();

      if (treeItem instanceof qx.ui.tree.TreeFolder) {
        treeItem.addOpenButton();
      }

      // The standard tree icon follows
      treeItem.addIcon();
      treeItem.setIcon(arguments.length >= 3 ? vIcon : "icon/16/places/user-desktop.png");

      // The label
      treeItem.addLabel(vLabel);

      // All else should be right justified
      treeItem.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      if (extraInfo) {
        let text;
        if (treeItem instanceof qx.ui.tree.TreeFile) {
          // Add a file size, date and mode
          text = new qx.ui.basic.Label(Math.round(Math.random() * 100) + "kb");
          text.setWidth(50);
          treeItem.addWidget(text);
        }

        text = new qx.ui.basic.Label("May " + Math.round(Math.random() * 30 + 1) + " 2005");
        text.setWidth(150);
        treeItem.addWidget(text);

        text = new qx.ui.basic.Label("-rw-r--r--");
        text.setWidth(80);
        treeItem.addWidget(text);
      }

      return treeItem;
    }
  }
});
