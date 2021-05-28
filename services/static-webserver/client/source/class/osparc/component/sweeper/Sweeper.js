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
    "iterationSelected": "qx.event.type.Data"
  },

  members: {
    __primaryStudy: null,
    __parametersTable: null,
    __iterationsSection: null,
    __iterationsTable: null,
    __selectedIteration: null,

    __buildSecondaryLayout: function(secondaryStudy) {
      const newParamBtn = new qx.ui.form.Button(this.tr("Open primary study")).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const primaryStudyId = secondaryStudy.getSweeper().getPrimaryStudyId();
        this.fireDataEvent("iterationSelected", primaryStudyId);
      });
      this._add(newParamBtn);
    },

    __buildPrimaryLayout: function() {
      const parametersSection = this.__buildParametersSection();
      this._add(parametersSection, {
        flex: 2
      });

      const iterationsSection = this.__buildIterationsSection();
      this._add(iterationsSection, {
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

    __buildIterationsSection: function() {
      const iterationsSection = this.__iterationsSection = new qx.ui.groupbox.GroupBox(this.tr("Iterations")).set({
        layout: new qx.ui.layout.VBox(5)
      });

      const iterationBtns = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const deleteIterationsBtn = this.__deleteIterationsBtn();
      iterationBtns.add(deleteIterationsBtn);
      const recreateIterationsBtn = this.__recreateIterationsBtn();
      iterationBtns.add(recreateIterationsBtn);
      iterationsSection.addAt(iterationBtns, 0);

      this.__rebuildIterationsTable();

      const openIterationsBtn = this.__openIterationsBtn = this.__createOpenIterationsBtn();
      openIterationsBtn.setEnabled(false);
      iterationsSection.addAt(openIterationsBtn, 2);
      openIterationsBtn.addListener("execute", () => {
        if (this.__selectedIteration) {
          this.fireDataEvent("iterationSelected", this.__selectedIteration);
        }
      });

      return iterationsSection;
    },

    __rebuildIterationsTable: function() {
      if (this.__iterationsTable) {
        this.__iterationsSection.remove(this.__iterationsTable);
      }

      const iterationsTable = this.__iterationsTable = new osparc.component.sweeper.Iterations(this.__primaryStudy);
      iterationsTable.addListener("cellTap", e => {
        if (this.__openIterationsBtn) {
          this.__openIterationsBtn.setEnabled(true);
        }
        const selectedRow = e.getRow();
        this.__selectedIteration = iterationsTable.getRowData(selectedRow)["StudyId"];
      });

      this.__iterationsSection.addAt(iterationsTable, 1, {
        flex: 1
      });

      return iterationsTable;
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

    __deleteIterationsBtn: function() {
      const deleteIterationsBtn = new osparc.ui.form.FetchButton(this.tr("Delete Iterations")).set({
        alignX: "left",
        allowGrowX: false
      });
      deleteIterationsBtn.addListener("execute", () => {
        deleteIterationsBtn.setFetching(true);
        this.__deleteIterations(deleteIterationsBtn)
          .then(() => {
            this.__rebuildIterationsTable();
          })
          .finally(() => {
            deleteIterationsBtn.setFetching(false);
          });
      }, this);
      return deleteIterationsBtn;
    },

    __recreateIterationsBtn: function() {
      const recreateIterationsBtn = new osparc.ui.form.FetchButton(this.tr("Recreate Iterations")).set({
        alignX: "right",
        allowGrowX: false
      });
      recreateIterationsBtn.addListener("execute", () => {
        recreateIterationsBtn.setFetching(true);
        this.__recreateIterations(recreateIterationsBtn)
          .then(() => {
            this.__rebuildIterationsTable();
          })
          .finally(() => {
            recreateIterationsBtn.setFetching(false);
          });
      }, this);
      return recreateIterationsBtn;
    },

    __deleteIterations: function() {
      return new Promise((resolve, reject) => {
        this.__primaryStudy.getSweeper().removeSecondaryStudies()
          .then(() => {
            const msg = this.tr("Iterations deleted");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg);
            resolve();
          });
      });
    },

    __recreateIterations: function() {
      return new Promise((resolve, reject) => {
        const primaryStudyData = this.__primaryStudy.serialize();
        this.__primaryStudy.getSweeper().recreateIterations(primaryStudyData)
          .then(secondaryStudyIds => {
            const msg = secondaryStudyIds.length + this.tr(" Iterations created");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg);
            resolve();
          });
      });
    },

    __createOpenIterationsBtn: function() {
      const openIterationBtn = new qx.ui.form.Button(this.tr("Open Iteration")).set({
        allowGrowX: false
      });
      return openIterationBtn;
    }
  }
});
