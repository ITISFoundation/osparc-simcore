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
 * If a file is deleted it fires "pathsDeleted" data event
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

    deleteEnabled: {
      check: "Boolean",
      init: true,
      nullable: true,
      apply: "__applyDeleteEnabled",
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

    __applyDeleteEnabled: function(value) {
      if (value === false) {
        this.getChildControl("delete-button").setEnabled(false);
      }
    },

    setItemSelected: function(selectedItem) {
      if (selectedItem) {
        this.__selection = [selectedItem];
        this.getChildControl("download-button").setEnabled(true);
        this.getChildControl("delete-button").setEnabled(this.isDeleteEnabled());
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
      this.getChildControl("delete-button").setEnabled(this.isDeleteEnabled());
      this.getChildControl("selected-label").resetValue();
    },

    __retrieveURLAndDownloadSelected: function() {
      if (this.isMultiSelect()) {
        if (this.__selection.length === 1 && osparc.file.FilesTree.isFile(this.__selection[0])) {
          this.__retrieveURLAndDownloadFile(this.__selection[0]);
        } else if (this.__selection.length > 1) {
          const paths = this.__selection.map(item => item.getPath());
          this.__retrieveURLAndExportData(paths);
        }
      } else if (this.__selection.length) {
        const selection = this.__selection[0];
        if (selection) {
          if (osparc.file.FilesTree.isFile(selection)) {
            this.__retrieveURLAndDownloadFile(selection);
          } else {
            const paths = [selection.getPath()];
            this.__retrieveURLAndExportData(paths);
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

    __retrieveURLAndExportData: function(paths) {
      const dataStore = osparc.store.Data.getInstance();
      const fetchPromise = dataStore.exportData(paths);
      const pollTasks = osparc.store.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise)
        .then(task => osparc.task.ExportData.exportDataTaskReceived(task))
        .catch(err => osparc.FlashMessenger.logError(err, this.tr("Unsuccessful files download")));
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
      if (toBeDeleted.length === 0) {
        return;
      }
      if (toBeDeleted[0].getLocation() != 0) {
        osparc.FlashMessenger.logAs(this.tr("You can only delete files in the local storage"), "WARNING");
        return;
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
      if (toBeDeleted.length === 0) {
        osparc.FlashMessenger.logAs(this.tr("Nothing to delete"), "ERROR");
        return;
      } else if (toBeDeleted.length > 0) {
        const paths = toBeDeleted.map(item => item.getPath());
        const dataStore = osparc.store.Data.getInstance();
        const fetchPromise = dataStore.deleteFiles(paths);
        const pollTasks = osparc.store.PollTasks.getInstance();
        pollTasks.createPollingTask(fetchPromise)
          .then(task => this.__deleteTaskReceived(task, paths))
          .catch(err => osparc.FlashMessenger.logError(err, this.tr("Unsuccessful files deletion")));
      }
    },

    __deleteTaskReceived: function(task, paths) {
      const taskUI = new osparc.task.TaskUI();
      taskUI.setIcon("@FontAwesome5Solid/trash/14");
      taskUI.setTitle(this.tr("Deleting files"));
      taskUI.setTask(task);
      osparc.task.TasksContainer.getInstance().addTaskUI(taskUI);

      const progressWindow = new osparc.ui.window.Progress(
        this.tr("Delete files"),
        "@FontAwesome5Solid/trash/14",
        this.tr("Deleting files..."),
      );
      if (task.getAbortHref()) {
        const cancelButton = progressWindow.addCancelButton();
        cancelButton.setLabel(this.tr("Ignore"));
        const abortButton = new qx.ui.form.Button().set({
          label: this.tr("Cancel"),
          center: true,
          minWidth: 100,
        });
        abortButton.addListener("execute", () => task.abortRequested());
        progressWindow.addButton(abortButton);
        abortButton.set({
          appearance: "danger-button",
        });
      }
      progressWindow.open();

      task.addListener("updateReceived", e => {
        const data = e.getData();
        if (data["task_progress"]) {
          if ("message" in data["task_progress"] && data["task_progress"]["message"]) {
            progressWindow.setMessage(data["task_progress"]["message"]);
          }
          progressWindow.setProgress(osparc.data.PollTask.extractProgress(data) * 100);
        }
      }, this);
      task.addListener("resultReceived", e => {
        osparc.FlashMessenger.logAs(this.tr("Items successfully deleted"), "INFO");
        this.fireDataEvent("pathsDeleted", paths);
        progressWindow.close();
      });
      task.addListener("taskAborted", () => {
        osparc.FlashMessenger.logAs(this.tr("Deletion aborted"), "WARNING");
        progressWindow.close();
      });
      task.addListener("pollingError", e => {
        const err = e.getData();
        osparc.FlashMessenger.logError(err);
        progressWindow.close();
      });
    },
  }
});
