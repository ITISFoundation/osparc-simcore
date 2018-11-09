/* global XMLHttpRequest */
qx.Class.define("qxapp.component.widget.FilePicker", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel, projectId) {
    this.base(arguments);

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    let tree = this.__tree = this._createChildControlImpl("treeMenu");
    tree.getSelection().addListener("change", this.__selectionChanged, this);

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

    this.__createConnections(nodeModel);

    this.setNodeModel(nodeModel);
    this.setProjectId(projectId);
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel"
    },

    projectId: {
      check: "String",
      init: ""
    }
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
      this.__getFiles();
    },

    __getFiles: function() {
      let filesTreePopulator = new qxapp.utils.FilesTreePopulator(this.__tree);
      filesTreePopulator.populateMyDocuments();

      let that = this;
      let delegate = this.__tree.getDelegate();
      delegate["configureItem"] = function(item) {
        item.addListener("dbltap", e => {
          that.__itemSelected(); // eslint-disable-line no-underscore-dangle
        }, that);
      };
      this.__tree.setDelegate(delegate);
    },

    __createConnections: function(nodeModel) {
      this.addListener("ItemSelected", function(data) {
        const itemPath = data.getData().itemPath;
        let outputs = nodeModel.getOutputs();
        outputs["outFile"].value = {
          store: "s3-z43",
          path: itemPath
        };
        this.fireEvent("Finished");
      }, this);
    },

    // Request to the server an upload URL.
    __retrieveURLAndUpload: function(file) {
      let store = qxapp.data.Store.getInstance();
      store.addListenerOnce("PresginedLink", e => {
        const presginedLinkData = e.getData();
        // presginedLinkData.locationId;
        // presginedLinkData.fileUuid;
        console.log(presginedLinkData);
        console.log(file);
        // const url = data["url"];
        this.__uploadFile(file, presginedLinkData.presginedLink);
      }, this);
      const download = false;
      const locationId = 0;
      // const location = "simcore.s3";
      // const bucketName = "simcore";
      const projectId = this.getProjectId();
      const nodeId = this.getNodeModel().getNodeId();
      const fileId = file.name;
      // const fileUuid = location +"/"+ bucketName +"/"+ projectId +"/"+ nodeId +"/"+ fileId;
      const fileUuid = projectId +"/"+ nodeId +"/"+ fileId;
      store.getPresginedLink(download, locationId, fileUuid);

      /*
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
      */
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

    __isFile: function(item) {
      let isFile = false;
      if (item["set"+qx.lang.String.firstUp("fileId")]) {
        isFile = true;
      }
      return isFile;
    },

    __selectionChanged: function() {
      let selection = this.__tree.getSelection();
      let selectedItem = selection.toArray()[0];
      let enabled = this.__isFile(selectedItem);
      this.__selectBtn.setEnabled(enabled);
    },

    __itemSelected: function() {
      let selection = this.__tree.getSelection();
      let selectedItem = selection.toArray()[0];
      const data = {
        itemPath: selectedItem.getFileId()
      };
      this.fireDataEvent("ItemSelected", data);
    }
  }
});
