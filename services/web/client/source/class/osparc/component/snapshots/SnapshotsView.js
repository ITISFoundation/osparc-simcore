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

qx.Class.define("osparc.component.snapshots.SnapshotsView", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    if (study.isSnapshot()) {
      const primaryStudyId = study.getSweeper().getPrimaryStudyId();
      const openPrimaryStudyParamBtn = new qx.ui.form.Button(this.tr("Open Main Study")).set({
        allowGrowX: false
      });
      openPrimaryStudyParamBtn.addListener("execute", () => {
        this.fireDataEvent("openPrimaryStudy", primaryStudyId);
      });
      this._add(openPrimaryStudyParamBtn);
    } else {
      this.__primaryStudy = study;
      const snapshotsSection = this.__buildSnapshotsSection();
      this._add(snapshotsSection, {
        flex: 1
      });
    }
  },

  events: {
    "openPrimaryStudy": "qx.event.type.Data",
    "openSnapshot": "qx.event.type.Data"
  },

  members: {
    __snapshotsSection: null,
    __snapshotsTable: null,
    __selectedSnapshot: null,
    __openSnapshotBtn: null,

    __buildSnapshotsSection: function() {
      const snapshotsSection = this.__snapshotsSection = new qx.ui.groupbox.GroupBox(this.tr("Snapshots")).set({
        layout: new qx.ui.layout.VBox(5)
      });

      const snapshotBtns = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const deleteSnapshotsBtn = this.__deleteSnapshotsBtn();
      snapshotBtns.add(deleteSnapshotsBtn);
      const recreateSnapshotsBtn = this.__recreateSnapshotsBtn();
      snapshotBtns.add(recreateSnapshotsBtn);
      snapshotsSection.addAt(snapshotBtns, 0);

      this.__rebuildSnapshotsTable();

      const openSnapshotBtn = this.__openSnapshotBtn = this.__createOpenSnapshotBtn();
      openSnapshotBtn.setEnabled(false);
      snapshotsSection.addAt(openSnapshotBtn, 2);
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
        if (this.__openSnapshotBtn) {
          this.__openSnapshotBtn.setEnabled(true);
        }
        const selectedRow = e.getRow();
        this.__selectedSnapshot = snapshotsTable.getRowData(selectedRow)["StudyId"];
      });

      this.__snapshotsSection.addAt(snapshotsTable, 1, {
        flex: 1
      });

      return snapshotsTable;
    },

    __deleteSnapshotsBtn: function() {
      const deleteSnapshotsBtn = new osparc.ui.form.FetchButton(this.tr("Delete Snapshots")).set({
        alignX: "left",
        allowGrowX: false
      });
      deleteSnapshotsBtn.addListener("execute", () => {
        deleteSnapshotsBtn.setFetching(true);
        this.__deleteSnapshots(deleteSnapshotsBtn)
          .then(() => {
            this.__rebuildSnapshotsTable();
          })
          .finally(() => {
            deleteSnapshotsBtn.setFetching(false);
          });
      }, this);
      return deleteSnapshotsBtn;
    },

    __recreateSnapshotsBtn: function() {
      const recreateSnapshotsBtn = new osparc.ui.form.FetchButton(this.tr("Recreate Snapshots")).set({
        alignX: "right",
        allowGrowX: false
      });
      recreateSnapshotsBtn.addListener("execute", () => {
        recreateSnapshotsBtn.setFetching(true);
        this.__recreateSnapshots(recreateSnapshotsBtn)
          .then(() => {
            this.__rebuildSnapshotsTable();
          })
          .finally(() => {
            recreateSnapshotsBtn.setFetching(false);
          });
      }, this);
      return recreateSnapshotsBtn;
    },

    __deleteSnapshots: function() {
      return new Promise((resolve, reject) => {
        this.__primaryStudy.getSweeper().removeSecondaryStudies()
          .then(() => {
            const msg = this.tr("Snapshots Deleted");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg);
            resolve();
          });
      });
    },

    __recreateSnapshots: function() {
      return new Promise((resolve, reject) => {
        const primaryStudyData = this.__primaryStudy.serialize();
        this.__primaryStudy.getSweeper().recreateSnapshots(primaryStudyData, this.__primaryStudy.getParameters())
          .then(secondaryStudyIds => {
            const msg = secondaryStudyIds.length + this.tr(" Snapshots Created");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg);
            resolve();
          });
      });
    },

    __createOpenSnapshotBtn: function() {
      const openSnapshotBtn = new qx.ui.form.Button(this.tr("Open Snapshot")).set({
        allowGrowX: false
      });
      return openSnapshotBtn;
    }
  }
});
