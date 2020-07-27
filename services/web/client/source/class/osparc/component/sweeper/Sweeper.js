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

    this._setLayout(new qx.ui.layout.VBox(5));

    if (study.getSweeper().getPrimaryStudyId()) {
      this.__buildSecondaryLayout(study);
    } else {
      this.__primaryStudy = study;
      this.__buildPrimaryLayout();
    }
  },

  statics: {
    popUpInWindow: function(parametersWidget) {
      const window = new osparc.ui.window.Window(qx.locale.Manager.tr("Parameters")).set({
        autoDestroy: true,
        layout: new qx.ui.layout.VBox(),
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        modal: true
      });
      window.add(parametersWidget);
      window.center();
      window.open();
      return window;
    }
  },

  events: {
    "iterationSelected": "qx.event.type.Data"
  },

  members: {
    __primaryStudy: null,
    __parametersTable: null,
    __iterationsTable: null,
    __selectedIteration: null,

    __buildSecondaryLayout: function(secondaryStudy) {
      const newParamBtn = new qx.ui.form.Button(this.tr("Open primary study")).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const primaryStudyId = secondaryStudy.getSweeper().getPrimaryStudyId()
        this.fireDataEvent("iterationSelected", primaryStudyId);

      });
      this._addAt(newParamBtn, 0);
    },

    __buildPrimaryLayout: function() {
      const newParamBtn = this.__createNewParamBtn();
      this._addAt(newParamBtn, 0);
      const parametersTable = this.__parametersTable = this.__createParametersTable().set({
        minWidth: 400,
        maxHeight: 200
      });
      this._addAt(parametersTable, 1);

      this._addAt(new qx.ui.core.Spacer(null, 10), 2);

      const recreateIterationsBtn = this.__recreateIterationsBtn();
      this._addAt(recreateIterationsBtn, 3);
      const iterationsTable = this.__iterationsTable = this.__createIterationsTable().set({
        minWidth: 400,
        maxHeight: 400
      });
      this._addAt(iterationsTable, 4);

      const openIterationsBtn = this.__openIterationsBtn = this.__createOpenIterationsBtn();
      openIterationsBtn.setEnabled(false);
      this._addAt(openIterationsBtn, 5);
      openIterationsBtn.addListener("execute", () => {
        if (this.__selectedIteration) {
          this.fireDataEvent("iterationSelected", this.__selectedIteration);
        }
      });
    },

    __createNewParamBtn: function() {
      const label = this.tr("Create new parameter");
      const newParamBtn = new qx.ui.form.Button(label).set({
        allowGrowX: false
      });
      newParamBtn.addListener("execute", () => {
        const subtitle = this.tr("Do not use whitespaces");
        const newParamName = new osparc.component.widget.Renamer(null, subtitle, label);
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

    __createParametersTable: function() {
      const params = new osparc.component.sweeper.Parameters(this.__primaryStudy);
      return params;
    },

    __recreateIterationsBtn: function() {
      const recreateIterationsBtn = new osparc.ui.form.FetchButton(this.tr("Recreate Iterations")).set({
        allowGrowX: false
      });
      recreateIterationsBtn.addListener("execute", () => {
        // recreate table
        if (this.__iterationsTable) {
          this._remove(this.__iterationsTable);
        }

        this.__recreateIterations(recreateIterationsBtn)
          .then(() => {
            const paramCombinations = this.__iterationsTable = this.__createIterationsTable().set({
              maxHeight: 400
            });
            this._addAt(paramCombinations, 4);
          });
      }, this);
      return recreateIterationsBtn;
    },

    __recreateIterations: function(recreateIterationsBtn) {
      return new Promise((resolve, reject) => {
        recreateIterationsBtn.setFetching(true);
        const primaryStudyData = this.__primaryStudy.serializeStudy();
        this.__primaryStudy.getSweeper().recreateIterations(primaryStudyData)
          .then(secondaryStudyIds => {
            recreateIterationsBtn.setFetching(false);
            const msg = secondaryStudyIds.length + this.tr(" iterations created");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg);
            resolve();
          });
      });
    },

    __createIterationsTable: function() {
      const iterations = new osparc.component.sweeper.Iterations(this.__primaryStudy);
      iterations.addListener("cellTap", e => {
        if (this.__openIterationsBtn) {
          this.__openIterationsBtn.setEnabled(true);
        }
        const selectedRow = e.getRow();
        this.__selectedIteration = iterations.getRowData(selectedRow)["StudyId"];
      });
      return iterations;
    },

    __createOpenIterationsBtn: function() {
      const openIterationBtn = new qx.ui.form.Button(this.tr("Open iteration")).set({
        allowGrowX: false
      });
      return openIterationBtn;
    }
  }
});
