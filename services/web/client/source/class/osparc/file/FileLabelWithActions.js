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

/**
 * A HBox containing a text field, download button and delete button.
 *
 *   It is used together with a virtual tree of files where the selection is displayed
 * in the text field and the download and delete are related to that selection.
 * Download and deleted methods are also provided.
 * If a file is deleted it fires "fileDeleted" data event
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let hBox = new osparc.file.FileLabelWithActions();
 *   this.getRoot().add(hBox);
 * </pre>
 */

qx.Class.define("osparc.file.FileLabelWithActions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    const downloadBtn = this.getChildControl("downloadBtn");
    downloadBtn.addListener("execute", e => {
      this.__retrieveURLAndDownload();
    }, this);

    const deleteBtn = this.getChildControl("deleteBtn");
    deleteBtn.addListener("execute", e => {
      this.__deleteFile();
    }, this);

    this._createChildControlImpl("selectedLabel");
  },

  events: {
    "fileDeleted": "qx.event.type.Data"
  },

  members: {
    __selection: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "downloadBtn":
          control = new qx.ui.toolbar.Button(this.tr("Download"), "@FontAwesome5Solid/cloud-download-alt/16");
          osparc.utils.Utils.setIdToWidget(control, "filesTreeDownloadBtn");
          this._add(control);
          break;
        case "deleteBtn":
          control = new qx.ui.toolbar.Button(this.tr("Delete"), "@FontAwesome5Solid/trash-alt/16");
          osparc.utils.Utils.setIdToWidget(control, "filesTreeDeleteBtn");
          this._add(control);
          break;
        case "selectedLabel":
          control = new osparc.ui.toolbar.Label();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    itemSelected: function(selectedItem) {
      const isFile = osparc.file.FilesTree.isFile(selectedItem);
      this.getChildControl("downloadBtn").setEnabled(isFile);
      this.getChildControl("deleteBtn").setEnabled(isFile);
      if (isFile) {
        this.__selection = selectedItem;
        this.getChildControl("selectedLabel").setValue(selectedItem.getFileId());
      } else {
        this.__selection = null;
        this.getChildControl("selectedLabel").setValue("");
      }
    },

    getItemSelected: function() {
      const selectedItem = this.__selection;
      if (selectedItem && osparc.file.FilesTree.isFile(selectedItem)) {
        return selectedItem;
      }
      return null;
    },

    // Request to the server an download
    __retrieveURLAndDownload: function() {
      let selection = this.getItemSelected();
      if (selection) {
        const fileId = selection.getFileId();
        let fileName = fileId.split("/");
        fileName = fileName[fileName.length-1];
        const download = true;
        const locationId = selection.getLocation();
        const dataStore = osparc.store.Data.getInstance();
        dataStore.getPresignedLink(download, locationId, fileId)
          .then(presignedLinkData => {
            if (presignedLinkData.presignedLink) {
              const link = presignedLinkData.presignedLink.link;
              const fileNameFromLink = osparc.utils.Utils.fileNameFromPresignedLink(link);
              fileName = fileNameFromLink ? fileNameFromLink : fileName;
              osparc.utils.Utils.downloadLink(link, "GET", fileName);
            }
          });
      }
    },

    __deleteFile: function() {
      let selection = this.getItemSelected();
      if (selection) {
        console.log("Delete ", selection);
        const fileId = selection.getFileId();
        const locationId = selection.getLocation();
        if (locationId !== 0 && locationId !== "0") {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only files in simcore.s3 can be deleted"));
          return false;
        }
        const dataStore = osparc.store.Data.getInstance();
        dataStore.addListenerOnce("deleteFile", e => {
          if (e) {
            this.fireDataEvent("fileDeleted", e.getData());
          }
        }, this);
        return dataStore.deleteFile(locationId, fileId);
      }
      return false;
    }
  }
});
