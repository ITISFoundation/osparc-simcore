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
      this.__primaryStudy = study;
      const snapshotsSection = this.__buildSnapshotsSection();
      this._add(snapshotsSection, {
        flex: 1
      });
    }
  },

  events: {
    "openSnapshot": "qx.event.type.Data"
  },

  members: {
    __snapshotsSection: null,
    __snapshotsTable: null,
    __snapshotPreview: null,
    __selectedSnapshot: null,
    __openSnapshotBtn: null,

    __buildSnapshotsSection: function() {
      const layout = new qx.ui.groupbox.GroupBox(this.tr("Snapshots")).set({
        layout: new qx.ui.layout.VBox(5)
      });

      const snapshotsSection = this.__snapshotsSection = new qx.ui.groupbox.GroupBox(this.tr("Snapshots")).set({
        layout: new qx.ui.layout.HBox(5)
      });

      this.__rebuildSnapshotsTable();
      this.__buildSnapshotPreview();

      const openSnapshotBtn = this.__openSnapshotBtn = this.__createOpenSnapshotBtn();
      openSnapshotBtn.setEnabled(false);
      layout.addAt(openSnapshotBtn, 2);
      openSnapshotBtn.addListener("execute", () => {
        if (this.__selectedSnapshot) {
          this.fireDataEvent("openSnapshot", this.__selectedSnapshot);
        }
      });

      return snapshotsSection;
    },

    __rebuildSnapshotsTable: function() {
      if (this.__snapshotsTable) {
        this.__snapshotsSection.remove(this.__snapshotsTable);
      }

      const snapshotsTable = this.__snapshotsTable = new osparc.component.snapshots.Snapshots(this.__primaryStudy);
      snapshotsTable.addListener("cellTap", e => {
        this.__snapshotsSelected(e);
      });

      this.__snapshotsSection.addAt(snapshotsTable, 0, {
        flex: 1
      });

      return snapshotsTable;
    },

    __buildSnapshotPreview: function() {
      const snapshotPreview = this.__snapshotPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.__snapshotsSection.addAt(snapshotPreview, 1, {
        flex: 1
      });
    },

    __loadSnapshotsPreview: function(snapshotData) {
      const params = {
        url: {
          "studyId": snapshotData["ParentId"],
          "snapshotId": snapshotData["SnapshotId"]
        }
      };
      osparc.data.Resources.getOne("snapshots", params)
        .then(snapshotResp => {
          if (!snapshotResp) {
            const msg = this.tr("Snapshot not found");
            throw new Error(msg);
          }
          fetch(snapshotResp["url_project"])
            .then(response => response.json())
            .then(data => {
              const studyData = data["data"];
              const study = new osparc.data.model.Study(studyData);
              study.buildWorkbench();
              const workbenchUIPreview = new osparc.component.workbench.WorkbenchUIPreview().set({
                study: study
              });
              workbenchUIPreview.loadModel(study.getWorkbench());
            });
        });
    },

    __createOpenSnapshotBtn: function() {
      const openSnapshotBtn = new qx.ui.form.Button(this.tr("Open Snapshot")).set({
        allowGrowX: false
      });
      return openSnapshotBtn;
    },

    __snapshotsSelected: function(e) {
      const selectedRow = e.getRow();
      this.__selectedSnapshot = this.__snapshotsTable.getRowData(selectedRow);

      this.__loadSnapshotsPreview(this.__selectedSnapshot);

      if (this.__openSnapshotBtn) {
        this.__openSnapshotBtn.setEnabled(true);
      }
    }
  }
});
