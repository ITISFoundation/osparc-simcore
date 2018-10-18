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

    let tree = this.__tree = this._createChildControlImpl("treeMenu");
    tree.getSelection().addListener("change", this.__selectionChanged, this);

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

    this.buildTree();

    this.__createConnections(node);
  },

  events: {
    "ItemSelected": "qx.event.type.Data",
    "Finished": "qx.event.type.Event"
  },

  members: {
    __tree: null,
    __selectBtn: null,
    __currentUserId: "ODEI-UUID",

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "addButton":
          control = new qx.ui.form.Button(this.tr("Add file(s)"));
          this._add(control);
          break;
        case "treeMenu":
          control = new qx.ui.tree.VirtualTree(null, "label", "children").set({
            openMode: "none"
          });
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

    buildTree: function() {
      const files = this.__getObjLists();
      let data = {
        label: this.__currentUserId,
        children: this.__convertModel(files),
        nodeId: this.__currentUserId
      };
      let newModel = qx.data.marshal.Json.createModel(data, true);
      let oldModel = this.__tree.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        this.__tree.setModel(newModel);
      }
    },

    __convertModel: function(files) {
      let children = [];
      for (let i=0; i<files.length; i++) {
        const file = files[i];
        let fileInTree = {
          label: file["location"],
          children: [{
            label: file["bucket_name"],
            children: []
          }]
        };
        let bucketChildren = fileInTree.children[0].children;
        let splitted = file["object_name"].split("/");
        if (file["location"] === "simcore.s3") {
          // simcore files
          if (splitted.length === 2) {
            // user file
            bucketChildren.push({
              label: file["user_name"],
              children: [{
                label: file["file_name"],
                fileId: file["file_uuid"]
              }]
            });
            children.push(fileInTree);
          } else if (splitted.length === 3) {
            // node file
            bucketChildren.push({
              label: file["project_name"],
              children: [{
                label: file["node_name"],
                children: [{
                  label: file["file_name"],
                  fileId: file["file_uuid"]
                }]
              }]
            });
            children.push(fileInTree);
          }
        } else {
          // other files
          bucketChildren.push({
            label: file["file_name"],
            fileId: file["file_uuid"]
          });
        }
      }
      return children;
    },

    __getObjLists: function() {
      const slotName = "listObjects";
      let socket = qxapp.wrappers.WebSocket.getInstance();
      socket.removeSlot(slotName);
      socket.on(slotName, function(data) {
        console.log(slotName, data);
      }, this);
      socket.emit(slotName);

      let data = qxapp.dev.fake.Data.getObjectList();
      console.log("Fake", slotName, data);
      return data;
    },

    __createConnections: function(node) {
      this.addListener("ItemSelected", function(data) {
        const itemPath = data.getData().itemPath;
        let outputs = node.getOutputs();
        outputs["outFile"].value = {
          store: "s3-z43",
          path: itemPath
        };
        this.fireEvent("Finished");
      }, this);
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
          this.buildTree();
        }
      };
    },

    __selectionChanged: function() {
      let selection = this.__tree.getSelection();
      let selectedItem = selection.toArray()[0];
      this.__selectBtn.setEnabled("fileId" in selectedItem);
    },

    __itemSelected: function() {
      let selection = this.__tree.getSelection();
      let selectedItem = selection.toArray()[0];
      if ("fileId" in selectedItem) {
        const data = {
          itemPath: selectedItem["fileId"]["file_uuid"]
        };
        this.fireDataEvent("ItemSelected", data);
      }
    }
  }
});
