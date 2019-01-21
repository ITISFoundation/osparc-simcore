/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global XMLHttpRequest */
qx.Class.define("qxapp.component.widget.FilePicker", {
  extend: qx.ui.core.Widget,

  construct: function(node, projectId) {
    this.base(arguments);

    this.setNode(node);
    this.setProjectId(projectId);

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    let tree = this.__tree = this._createChildControlImpl("filesTree");
    tree.addListener("selectionChanged", this.__selectionChanged, this);
    tree.addListener("itemSelected", this.__itemSelected, this);

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

    this.__initResources();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node"
    },

    projectId: {
      check: "String",
      init: ""
    }
  },

  events: {
    "finished": "qx.event.type.Event"
  },

  members: {
    __tree: null,
    __selectBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filesTree":
          control = new qxapp.component.widget.FilesTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "progressBox":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 1);
          break;
        case "addButton":
          control = new qx.ui.form.Button(this.tr("Add file(s)"));
          this._add(control);
          break;
        case "selectButton":
          control = new qx.ui.form.Button(this.tr("Select"));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __initResources: function() {
      this.__tree.populateTree();
    },

    __selectionChanged: function() {
      const data = this.__tree.getSelectedFile();
      if (data) {
        const isFile = data["isFile"];
        this.__selectBtn.setEnabled(isFile);
      } else {
        this.__selectBtn.setEnabled(false);
      }
    },

    __itemSelected: function() {
      let data = this.__tree.getSelectedFile();
      if (data && data["isFile"]) {
        let selectedItem = data["selectedItem"];
        let outputs = this.getNode().getOutputs();
        outputs["outFile"].value = {
          store: selectedItem.getLocation(),
          path: selectedItem.getFileId()
        };
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    },

    // Request to the server an upload URL.
    __retrieveURLAndUpload: function(file) {
      let store = qxapp.data.Store.getInstance();
      store.addListenerOnce("presginedLink", e => {
        const presginedLinkData = e.getData();
        // presginedLinkData.locationId;
        // presginedLinkData.fileUuid;
        console.log(file);
        if (presginedLinkData.presginedLink) {
          this.__uploadFile(file, presginedLinkData.presginedLink.link);
        }
      }, this);
      const download = false;
      const locationId = 0;
      const projectId = this.getProjectId();
      const nodeId = this.getNode().getNodeId();
      const fileId = file.name;
      const fileUuid = projectId +"/"+ nodeId +"/"+ fileId;
      store.getPresginedLink(download, locationId, fileUuid);
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

      // From https://github.com/minio/cookbook/blob/master/docs/presigned-put-upload-via-browser.md
      let xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", e => {
        if (e.lengthComputable) {
          const percentComplete = e.loaded / e.total * 100;
          progressBar.setValue(percentComplete);
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      xhr.onload = () => {
        if (xhr.status == 200) {
          console.log("Uploaded", file.name);
          hBox.destroy();
          this.__initResources();
        } else {
          console.log(xhr.response);
        }
      };
      xhr.open("PUT", url, true);
      xhr.send(file);
    }
  }
});
