/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @ignore(fetch)
 */

qx.Class.define("osparc.component.snapshots.SnapshotsView", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    if (study.hasSnapshots()) {
      this.__study = study;
      this.__buildLayout();
    }
  },

  events: {
    "updateSnapshot": "qx.event.type.Data",
    "openSnapshot": "qx.event.type.Data"
  },

  members: {
    __snapshotsSection: null,
    __snapshotsTable: null,
    __gitGraphLayout: null,
    __gitGraphWrapper: null,
    __snapshotPreview: null,
    __editSnapshotBtn: null,
    __openSnapshotBtn: null,
    __snapshots: null,
    __currentSnapshot: null,
    __selectedSnapshotId: null,

    __buildLayout: function() {
      const snapshotsSection = this.__snapshotsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(snapshotsSection, {
        flex: 1
      });
      this.__rebuildSnapshots();
      this.__buildSnapshotPreview();

      const buttonsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this._add(buttonsSection);

      const editSnapshotBtn = this.__editSnapshotBtn = this.__createEditSnapshotBtn();
      editSnapshotBtn.setEnabled(false);
      editSnapshotBtn.addListener("execute", () => {
        if (this.__selectedSnapshotId) {
          this.__editSnapshot(this.__selectedSnapshotId);
        }
      });
      buttonsSection.add(editSnapshotBtn);

      const openSnapshotBtn = this.__openSnapshotBtn = this.__createOpenSnapshotBtn();
      openSnapshotBtn.setEnabled(false);
      openSnapshotBtn.addListener("execute", () => {
        if (this.__selectedSnapshotId) {
          this.fireDataEvent("openSnapshot", this.__selectedSnapshotId);
        }
      });
      buttonsSection.add(openSnapshotBtn);
    },

    __rebuildSnapshots: function() {
      Promise.all([
        this.__study.getSnapshots(),
        this.__study.getCurrentSnapshot()
      ])
        .then(values => {
          this.__snapshots = values[0];
          this.__currentSnapshot = values[1];
          this.__rebuildSnapshotsTable();
          this.__rebuildSnapshotsGraph();
        });
    },

    __rebuildSnapshotsTable: function() {
      if (this.__snapshotsTable) {
        this.__snapshotsSection.remove(this.__snapshotsTable);
      }

      const snapshotsTable = this.__snapshotsTable = new osparc.component.snapshots.Snapshots();
      snapshotsTable.populateTable(this.__snapshots);
      snapshotsTable.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const snapshotId = snapshotsTable.getRowData(selectedRow)["Id"];
        this.__snapshotSelected(snapshotId);
      });

      this.__snapshotsSection.addAt(snapshotsTable, 0, {
        width: "40%"
      });
    },

    __rebuildSnapshotsGraph: function() {
      if (this.__gitGraphLayout) {
        this.__snapshotsSection.remove(this.__gitGraphLayout);
      }

      const gitGraphLayout = this.__gitGraphLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      const gitGraphCanvas = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
      const gitGraphInteract = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      gitGraphLayout.add(gitGraphCanvas, {
        top: 20,
        right: 0,
        bottom: 0,
        left: 0
      });
      gitGraphLayout.add(gitGraphInteract, {
        top: 20 + 2,
        right: 0,
        bottom: 0,
        left: 0
      });

      gitGraphCanvas.addListenerOnce("appear", () => {
        const gitGraphWrapper = this.__gitGraphWrapper = new osparc.wrapper.GitGraph();
        gitGraphWrapper.init(gitGraphCanvas, gitGraphInteract)
          .then(() => gitGraphWrapper.populateGraph(this.__snapshots, this.__currentSnapshot));
        gitGraphWrapper.addListener("snapshotTap", e => {
          const snapshotId = e.getData();
          this.__snapshotSelected(snapshotId);
        });
      });

      this.__snapshotsSection.addAt(gitGraphLayout, 1, {
        width: "20%"
      });
    },

    __buildSnapshotPreview: function() {
      const snapshotPreview = this.__snapshotPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.__snapshotsSection.addAt(snapshotPreview, 2, {
        width: "40%"
      });
    },

    __loadSnapshotsPreview: function(snapshotId) {
      const params = {
        url: {
          "studyId": this.__study.getUuid(),
          "snapshotId": snapshotId
        }
      };
      osparc.data.Resources.fetch("snapshots", "preview", params)
        .then(data => {
          const studyData = this.__study.serialize();
          studyData["workbench"] = data["workbench"];
          studyData["ui"] = data["ui"];
          const study = new osparc.data.model.Study(studyData);
          study.buildWorkbench();
          study.setReadOnly(true);
          this.__snapshotPreview.set({
            study: study
          });
          this.__snapshotPreview.loadModel(study.getWorkbench());
        });
    },

    __createEditSnapshotBtn: function() {
      const editSnapshotBtn = new qx.ui.form.Button(this.tr("Edit Snapshot")).set({
        allowGrowX: false
      });
      return editSnapshotBtn;
    },

    __createOpenSnapshotBtn: function() {
      const openSnapshotBtn = new qx.ui.form.Button(this.tr("Open Snapshot")).set({
        allowGrowX: false
      });
      return openSnapshotBtn;
    },

    __editSnapshot: function(snapshotId) {
      const selectedSnapshot = this.__snapshots.find(snapshot => snapshot["id"] === snapshotId);
      if (selectedSnapshot) {
        const editSnapshotView = new osparc.component.snapshots.EditSnapshotView();
        const tagCtrl = editSnapshotView.getChildControl("tags");
        tagCtrl.setValue(selectedSnapshot["tags"][0]);
        const msgCtrl = editSnapshotView.getChildControl("message");
        msgCtrl.setValue(selectedSnapshot["message"]);
        const title = this.tr("Edit Snapshot");
        const win = osparc.ui.window.Window.popUpInWindow(editSnapshotView, title, 400, 180);
        editSnapshotView.addListener("takeSnapshot", () => {
          const params = {
            url: {
              "studyId": this.__study.getUuid(),
              "snapshotId": snapshotId
            },
            data: {
              "tag": editSnapshotView.getTag(),
              "message": editSnapshotView.getMessage()
            }
          };
          osparc.data.Resources.fetch("snapshots", "updateSnapshot", params)
            .then(() => {
              this.__rebuildSnapshots();
            })
            .catch(err => osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR"));
          win.close();
        }, this);
        editSnapshotView.addListener("cancel", () => {
          win.close();
        }, this);
      }
    },

    __snapshotSelected: function(snapshotId) {
      this.__selectedSnapshotId = snapshotId;

      if (this.__snapshotsTable) {
        this.__snapshotsTable.setSelection(snapshotId);
      }

      if (this.__gitGraphWrapper) {
        this.__gitGraphWrapper.setSelection(snapshotId);
      }

      this.__loadSnapshotsPreview(snapshotId);

      if (this.__editSnapshotBtn) {
        this.__editSnapshotBtn.setEnabled(true);
      }

      if (this.__openSnapshotBtn) {
        this.__openSnapshotBtn.setEnabled(true);
      }
    }
  }
});
