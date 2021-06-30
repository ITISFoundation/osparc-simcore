/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.sweeper.Sweeper", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    if (study.getSweeper().getPrimaryStudyId()) {
      this.__buildSecondaryLayout(study);
    } else {
      this.__primaryStudy = study;
      this.__buildPrimaryLayout();
    }
  },

  events: {
    "snapshotSelected": "qx.event.type.Data"
  },

  members: {
    __primaryStudy: null,
    __parametersTable: null,
    __snapshotsSection: null,
    __snapshotsTable: null,
    __selectedSnapshot: null,
    __openSnapshotBtn: null,

    __buildSecondaryLayout: function(secondaryStudy) {
      const newParamBtn = new qx.ui.form.Button(this.tr("Open primary study")).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const primaryStudyId = secondaryStudy.getSweeper().getPrimaryStudyId();
        this.fireDataEvent("snapshotSelected", primaryStudyId);
      });
      this._add(newParamBtn);
    },

    __buildPrimaryLayout: function() {
      const parametersSection = this.__buildParametersSection();
      this._add(parametersSection, {
        flex: 2
      });

      const snapshotSection = this.__buildSnapshotsSection();
      this._add(snapshotSection, {
        flex: 3
      });
    },

    __buildParametersSection: function() {
      const parametersSection = new qx.ui.groupbox.GroupBox(this.tr("Parameters")).set({
        layout: new qx.ui.layout.VBox(5)
      });
      const newParamBtn = this.__createNewParamBtn();
      parametersSection.add(newParamBtn);

      const parametersTable = this.__parametersTable = new osparc.component.sweeper.Parameters(this.__primaryStudy);
      parametersSection.add(parametersTable, {
        flex: 1
      });
      return parametersSection;
    },

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
          this.fireDataEvent("snapshotSelected", this.__selectedSnapshot);
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

    __createNewParamBtn: function() {
      const label = this.tr("Create new Parameter");
      const newParamBtn = new qx.ui.form.Button(label).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const newParamName = new osparc.component.widget.Renamer(null, null, label);
        newParamName.addListener("labelChanged", e => {
          const primaryStudy = this.__primaryStudy;
          let newParameterLabel = e.getData()["newLabel"];
          newParameterLabel = newParameterLabel.replace(" ", "_");
          if (primaryStudy.getSweeper().parameterLabelExists(newParameterLabel)) {
            const msg = this.tr("Parameter name already exists");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
          } else {
            primaryStudy.getSweeper().addNewParameter(newParameterLabel);
            this.__parametersTable.updateTable();
            newParamName.close();
          }
        }, this);
        newParamName.center();
        newParamName.open();
      }, this);
      return newParamBtn;
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
        this.__primaryStudy.getSweeper().recreateSnapshots(primaryStudyData)
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
