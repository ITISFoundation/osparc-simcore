/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global XMLHttpRequest */

/**
 * Widget that provides a way to upload files to S3
 *
 *   It consists of a VBox containing a button that pops up a dialogue for selecting multiple files and
 * progerss bars for showing the uploading status.
 *
 *   When selecting the file to be uploaded this widget will ask for a presigned link where the file can be put
 * and start the file transimision via XMLHttpRequest. If the uplaod is successful, "fileAdded" data event will
 * be fired.
 *
 *   This class also accepts a Node and StudyID that are used for putting the file in the correct folder strucutre.
 * If are not provided, random uuids will be used.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filesAdd = new osparc.file.FilesAdd(this.tr("Add file(s)"));
 *   this.getRoot().add(filesAdd);
 * </pre>
 */

qx.Class.define("osparc.file.FilesAdd", {
  extend: qx.ui.core.Widget,

  /**
    * @param label {String} Text to be displayed in the button
    */
  construct: function(label = this.tr("Add file(s)")) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    const input = new qx.html.Input("file", {
      display: "none"
    }, {
      multiple: true
    });
    this.getContentElement().add(input);

    const btn = this._createChildControlImpl("addButton").set({
      label: label
    });
    btn.addListener("execute", e => {
      input.getDomElement().click();
    });

    input.addListener("change", e => {
      const files = input.getDomElement().files;
      for (let i=0; i<files.length; i++) {
        this.retrieveUrlAndUpload(files[i]);
      }
    }, this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
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
          this._addAt(control, 0);
          break;
        case "addButton":
          control = new qx.ui.toolbar.Button();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    // Request to the server an upload URL.
    retrieveUrlAndUpload: function(file) {
      const dataStore = osparc.store.Data.getInstance();
      dataStore.addListenerOnce("presignedLink", e => {
        const presignedLinkData = e.getData();
        file["location"] = presignedLinkData.locationId;
        file["path"] = presignedLinkData.fileUuid;
        if (presignedLinkData.presignedLink) {
          this.__uploadFile(file, presignedLinkData.presignedLink.link);
        }
      }, this);
      const download = false;
      const locationId = 0;
      const studyId = this.__getStudyId();
      const nodeId = this.getNode() ? this.getNode().getNodeId() : osparc.utils.Utils.uuidv4();
      const fileId = file.name;
      const fileUuid = studyId +"/"+ nodeId +"/"+ fileId;
      dataStore.getPresignedLink(download, locationId, fileUuid);
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: function(file, url) {
      const hBox = this._createChildControlImpl("progressBox");
      const label = new qx.ui.basic.Atom(file.name);
      const progressBar = new osparc.ui.toolbar.ProgressBar();
      hBox.add(label);
      hBox.add(progressBar);

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
          file.dataset = this.__getStudyId();
          this.fireDataEvent("fileAdded", file);
        } else {
          console.log(xhr.response);
        }
      };
      xhr.open("PUT", url, true);
      xhr.send(file);
    },

    __getStudyId: function() {
      return this.getWorkbench().getStudy()
        .getUuid();
    }
  }
});
