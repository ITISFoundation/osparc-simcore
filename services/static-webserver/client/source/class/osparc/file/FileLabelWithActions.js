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

    this._setLayout(new qx.ui.layout.HBox(10));

    this.getChildControl("spacer");
    this.getChildControl("selected-label");

    const downloadBtn = this.getChildControl("download-button");
    downloadBtn.addListener("execute", () => this.__retrieveURLAndDownloadSelected(), this);

    const deleteBtn = this.getChildControl("delete-button");
    deleteBtn.addListener("execute", () => this.__deleteSelected(), this);
  },

  events: {
    "fileDeleted": "qx.event.type.Data"
  },

  properties: {
    multiSelect: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelect",
      apply: "__enableMultiSelection",
    },
  },

  members: {
    __selection: null,
    __multiSelection: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "spacer":
          control = new qx.ui.core.Spacer();
          this._add(control, {
            flex: 1
          });
          break;
        case "selected-label":
          control = new qx.ui.basic.Label().set({
            alignY: "middle"
          });
          this._add(control);
          break;
        case "download-button":
          control = new qx.ui.form.Button(this.tr("Download"), "@FontAwesome5Solid/cloud-download-alt/16");
          osparc.utils.Utils.setIdToWidget(control, "filesTreeDownloadBtn");
          this._add(control);
          break;
        case "delete-button":
          control = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/16").set({
            appearance: "danger-button"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __enableMultiSelection: function() {
      this.resetItemSelected();
      this.__multiSelection = [];
    },

    setItemSelected: function(selectedItem) {
      if (selectedItem) {
        const isFile = osparc.file.FilesTree.isFile(selectedItem);
        this.getChildControl("download-button").setEnabled(isFile);
        this.getChildControl("delete-button").setEnabled(isFile);
        const selectedLabel = this.getChildControl("selected-label");
        if (isFile) {
          this.__selection = selectedItem;
          selectedLabel.set({
            value: selectedItem.getLabel(),
            toolTipText: selectedItem.getFileId()
          });
        } else {
          this.__selection = null;
          selectedLabel.set({
            value: "",
            toolTipText: ""
          });
        }
      } else {
        this.resetItemSelected();
      }
    },

    setMultiItemSelected: function(multiSelectionData) {
      this.__multiSelection = multiSelectionData;
      if (multiSelectionData && multiSelectionData.length) {
        if (multiSelectionData.length === 1) {
          this.setItemSelected(multiSelectionData[0]);
        } else {
          const selectedLabel = this.getChildControl("selected-label");
          selectedLabel.set({
            value: multiSelectionData.length + " files"
          });
        }
      } else {
        this.resetItemSelected();
      }
    },

    resetItemSelected: function() {
      this.__selection = null;
      this.__multiSelection = [];
      this.getChildControl("download-button").setEnabled(false);
      this.getChildControl("delete-button").setEnabled(false);
      this.getChildControl("selected-label").resetValue();
    },

    getItemSelected: function() {
      const selectedItem = this.__selection;
      if (selectedItem && osparc.file.FilesTree.isFile(selectedItem)) {
        return selectedItem;
      }
      return null;
    },

    __retrieveURLAndDownloadSelected: function() {
      if (this.isMultiSelect()) {
        this.__multiSelection.forEach(selection => {
          this.__retrieveURLAndDownloadFile(selection);
        });
      } else {
        const selection = this.getItemSelected();
        if (selection) {
          this.__retrieveURLAndDownloadFile(selection);
        }
      }
    },

    __deleteSelected: function() {
      if (this.isMultiSelect()) {
        const requests = [];
        this.__multiSelection.forEach(selection => {
          const request = this.__deleteFile(selection);
          if (request) {
            requests.push(request);
          }
        });
        Promise.all(requests)
          .then(datas => {
            if (datas.length) {
              this.fireDataEvent("fileDeleted", datas[0]);
              osparc.FlashMessenger.getInstance().logAs(this.tr("Files successfully deleted"), "ERROR");
            }
          });
        requests
      } else {
        const selection = this.getItemSelected();
        if (selection) {
          const request = this.__deleteFile(selection);
          if (request) {
            request
              .then(data => {
                this.fireDataEvent("fileDeleted", data);
                osparc.FlashMessenger.getInstance().logAs(this.tr("File successfully deleted"), "ERROR");
              });
          }
        }
      }
    },

    __retrieveURLAndDownloadFile: function(file) {
      const fileId = file.getFileId();
      const locationId = file.getLocation();
      osparc.utils.Utils.retrieveURLAndDownload(locationId, fileId)
        .then(data => {
          if (data) {
            osparc.DownloadLinkTracker.getInstance().downloadLinkUnattended(data.link, data.fileName);
          }
        });
    },

    __deleteFile: function(file) {
      const fileId = file.getFileId();
      const locationId = file.getLocation();
      if (locationId !== 0 && locationId !== "0") {
        osparc.FlashMessenger.getInstance().logAs(this.tr("Only files in simcore.s3 can be deleted"));
      }
      const dataStore = osparc.store.Data.getInstance();
      return dataStore.deleteFile(locationId, fileId);
    },
  }
});
