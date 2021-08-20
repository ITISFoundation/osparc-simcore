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
    __selectedSnapshot: null,
    __openSnapshotBtn: null,

    __buildSnapshotsSection: function() {
      const snapshotsSection = this.__snapshotsSection = new qx.ui.groupbox.GroupBox(this.tr("Snapshots")).set({
        layout: new qx.ui.layout.VBox(5)
      });

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
        this.__selectedSnapshot = snapshotsTable.getRowData(selectedRow);
      });

      this.__snapshotsSection.addAt(snapshotsTable, 1, {
        flex: 1
      });

      return snapshotsTable;
    },

    __createOpenSnapshotBtn: function() {
      const openSnapshotBtn = new qx.ui.form.Button(this.tr("Open Snapshot")).set({
        allowGrowX: false
      });
      return openSnapshotBtn;
    }
  }
});
