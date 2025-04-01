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

    this.__selection = [];
  },

  events: {
    "fileDeleted": "qx.event.type.Data",
    "pathsDeleted": "qx.event.type.Data",
  },

  properties: {
    multiSelect: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelect",
      apply: "__changeMultiSelection",
    },
  },

  members: {
    __selection: null,

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

    __changeMultiSelection: function() {
      if (this.__selection.length > 1) {
        this.resetSelection();
      }
    },

    setItemSelected: function(selectedItem) {
      if (selectedItem) {
        this.__selection = [selectedItem];
        const isFile = osparc.file.FilesTree.isFile(selectedItem);
        this.getChildControl("download-button").setEnabled(isFile);
        this.getChildControl("delete-button").setEnabled(true); // folders can also be deleted
        this.getChildControl("selected-label").setValue(selectedItem.getLabel());
      } else {
        this.resetSelection();
      }
    },

    setMultiItemSelected: function(multiSelectionData) {
      this.__selection = multiSelectionData;
      if (multiSelectionData && multiSelectionData.length) {
        if (multiSelectionData.length === 1) {
          this.setItemSelected(multiSelectionData[0]);
        } else {
          const selectedLabel = this.getChildControl("selected-label");
          selectedLabel.set({
            value: multiSelectionData.length + " items"
          });
        }
      } else {
        this.resetSelection();
      }
    },

    resetSelection: function() {
      this.__selection = [];
      this.getChildControl("download-button").setEnabled(false);
      this.getChildControl("delete-button").setEnabled(false);
      this.getChildControl("selected-label").resetValue();
    },

    __retrieveURLAndDownloadSelected: function() {
      if (this.isMultiSelect()) {
        this.__selection.forEach(selection => {
          if (selection && osparc.file.FilesTree.isFile(selection)) {
            this.__retrieveURLAndDownloadFile(selection);
          }
        });
      } else if (this.__selection.length) {
        const selection = this.__selection[0];
        if (selection && osparc.file.FilesTree.isFile(selection)) {
          this.__retrieveURLAndDownloadFile(selection);
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

    __deleteSelected: function() {
      const toBeDeleted = [];
      let isFolderSelected = false;
      if (this.isMultiSelect()) {
        this.__selection.forEach(selection => {
          if (selection) {
            toBeDeleted.push(selection);
            if (osparc.file.FilesTree.isDir(selection)) {
              isFolderSelected = true;
            }
          }
        });
      } else if (this.__selection.length) {
        const selection = this.__selection[0];
        if (selection) {
          toBeDeleted.push(selection);
          if (osparc.file.FilesTree.isDir(selection)) {
            isFolderSelected = true;
          }
        }
      }

      let msg = this.tr("This action cannot be undone.");
      msg += isFolderSelected ? ("<br>"+this.tr("All contents within the folders will be deleted.")) : "";
      msg += "<br>" + this.tr("Do you want to proceed?");
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.__doDeleteSelected(toBeDeleted);
        }
      }, this);
    },

    __doDeleteSelected: function(toBeDeleted) {
      let request = null;
      if (toBeDeleted.length === 0) {
        osparc.FlashMessenger.logAs(this.tr("Nothing to delete"), "ERROR");
        return;
      } else if (toBeDeleted.length === 1) {
        const selection = toBeDeleted[0];
        if (selection) {
          if (osparc.file.FilesTree.isFile(selection)) {
            request = this.__deleteItem(selection.getFileId(), selection.getLocation());
          } else {
            request = this.__deleteItem(selection.getPath(), selection.getLocation());
          }
          request
            .then(datas => {
              if (datas.length) {
                this.fireDataEvent("fileDeleted", datas[0]);
                osparc.FlashMessenger.logAs(this.tr("Items successfully deleted"), "INFO");
              }
            });
        }
      } else if (toBeDeleted.length > 1) {
        const paths = toBeDeleted.map(item => item.getPath());
        const dataStore = osparc.store.Data.getInstance();
        const fetchPromise = dataStore.deleteFiles(paths);
        const pollTasks = osparc.store.PollTasks.getInstance();
        const interval = 1000;
        pollTasks.createPollingTask(fetchPromise, interval)
          .then(task => {
            task.addListener("resultReceived", e => {
              this.fireDataEvent("pathsDeleted", paths);
            });
          })
          .catch(err => osparc.FlashMessenger.logError(err, this.tr("Unsuccessful files deletion")));
      }
    },

    __deleteItem: function(itemId, locationId) {
      if (locationId !== 0 && locationId !== "0") {
        osparc.FlashMessenger.logAs(this.tr("Externally managed items cannot be deleted"));
        return null;
      }
      const dataStore = osparc.store.Data.getInstance();
      return dataStore.deleteFile(locationId, itemId);
    },
  }
});
