/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global XMLHttpRequest */
qx.Class.define("qxapp.component.widget.FilesAdd", {
  extend: qx.ui.core.Widget,

  construct: function(label = this.tr("Add file(s)")) {
    this.base(arguments);

    let filesAddLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filesAddLayout);

    // Create a button
    let input = new qx.html.Input("file", {
      display: "none"
    }, {
      multiple: true
    });

    this.getContentElement().add(input);

    let btn = this._createChildControlImpl("addButton").set({
      label: label
    });
    // Add an event listener
    btn.addListener("execute", e => {
      input.getDomElement().click();
    });

    input.addListener("change", e => {
      let files = input.getDomElement().files;
      for (let i=0; i<files.length; i++) {
        this.__retrieveURLAndUpload(files[i]);
      }
    }, this);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: true
    },

    projectId: {
      check: "String",
      init: "",
      nullable: true
    }
  },

  events: {
    "fileAdded": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "progressBox":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 1);
          break;
        case "addButton":
          control = new qx.ui.form.Button();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
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
      const projectId = this.getProjectId() || qxapp.utils.Utils.uuidv4();
      const nodeId = this.getNode() ? this.getNode().getNodeId() : qxapp.utils.Utils.uuidv4();
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
          this.fireDataEvent("fileAdded", file);
        } else {
          console.log(xhr.response);
        }
      };
      xhr.open("PUT", url, true);
      xhr.send(file);
    }
  }
});
