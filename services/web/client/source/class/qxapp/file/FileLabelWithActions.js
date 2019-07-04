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
 *   let hBox = new qxapp.file.FileLabelWithActions();
 *   this.getRoot().add(hBox);
 * </pre>
 */

qx.Class.define("qxapp.file.FileLabelWithActions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox(5));

    let fileLabelWithActionsLayout = new qx.ui.layout.HBox(5);
    this._setLayout(fileLabelWithActionsLayout);

    this.__selectedLabel = this._createChildControlImpl("selectedLabel");

    let downloadBtn = this._createChildControlImpl("downloadBtn");
    downloadBtn.addListener("execute", e => {
      this.__retrieveURLAndDownload();
    }, this);

    let deleteBtn = this._createChildControlImpl("deleteBtn");
    deleteBtn.addListener("execute", e => {
      this.__deleteFile();
    }, this);
  },

  events: {
    "fileDeleted": "qx.event.type.Data"
  },

  members: {
    __selectedLabel: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "selectedLabel":
          control = new qx.ui.basic.Label().set({
            decorator: "main",
            backgroundColor: "white",
            allowGrowX: true,
            height: 24
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "downloadBtn":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/cloud-download-alt/24"
          });
          this._add(control);
          break;
        case "deleteBtn":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/trash-alt/24"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    itemSelected: function(selectedItem, isFile) {
      if (isFile) {
        this.__selection = selectedItem;
        this.__selectedLabel.setValue(selectedItem.getFileId());
      } else {
        this.__selection = null;
        this.__selectedLabel.setValue("");
      }
    },

    __getItemSelected: function() {
      let selectedItem = this.__selection;
      if (selectedItem && qxapp.file.FilesTree.isFile(selectedItem)) {
        return selectedItem;
      }
      return null;
    },

    // Request to the server an download
    __retrieveURLAndDownload: function() {
      let selection = this.__getItemSelected();
      if (selection) {
        const fileId = selection.getFileId();
        let fileName = fileId.split("/");
        fileName = fileName[fileName.length-1];
        let store = qxapp.data.Store.getInstance();
        store.addListenerOnce("presignedLink", e => {
          const presignedLinkData = e.getData();
          console.log(presignedLinkData.presignedLink);
          if (presignedLinkData.presignedLink) {
            qxapp.utils.Utils.downloadLink(presignedLinkData.presignedLink.link, fileName);
          }
        }, this);
        const download = true;
        const locationId = selection.getLocation();
        store.getPresignedLink(download, locationId, fileId);
      }
    },

    __deleteFile: function() {
      let selection = this.__getItemSelected();
      if (selection) {
        console.log("Delete ", selection);
        const fileId = selection.getFileId();
        const locationId = selection.getLocation();
        let store = qxapp.data.Store.getInstance();
        store.addListenerOnce("deleteFile", e => {
          if (e) {
            this.fireDataEvent("fileDeleted", e.getData());
          }
        }, this);
        return store.deleteFile(locationId, fileId);
      }
      return false;
    }
  }
});
