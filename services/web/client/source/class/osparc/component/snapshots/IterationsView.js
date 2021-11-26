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

qx.Class.define("osparc.component.snapshots.IterationsView", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__study = study;
    this.__iterations = [];
    this.__buildLayout();
  },

  events: {
    "openIteration": "qx.event.type.Data"
  },

  members: {
    __study: null,
    __iterations: null,
    __iterationsSection: null,
    __iterationsTable: null,
    __iterationPreview: null,
    __openIterationBtn: null,
    __selectedIterationId: null,

    __buildLayout: function() {
      const iterationsSection = this.__iterationsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(iterationsSection, {
        flex: 1
      });
      this.__rebuildIterations();
      this.__buildIterationPreview();

      const buttonsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this._add(buttonsSection);

      const openIterationBtn = this.__openIterationBtn = this.__createOpenIterationBtn();
      openIterationBtn.setEnabled(false);
      openIterationBtn.addListener("execute", () => {
        if (this.__selectedIterationId) {
          this.fireDataEvent("openIteration", this.__selectedIterationId);
        }
      });
      buttonsSection.add(openIterationBtn);
    },

    __rebuildIterations: function() {
      this.__study.getIterations()
        .then(iterations => {
          if (iterations.length) {
            const iterationPromises = [];
            iterations.forEach(iteration => {
              const params = {
                url: {
                  "studyId": iteration["wcopy_project_id"]
                }
              };
              iterationPromises.push(osparc.data.Resources.getOne("studies", params));
            });
            Promise.all(iterationPromises)
              .then(values => {
                this.__iterations = values;
                this.__rebuildIterationsTable();
              });
          }
        });
    },

    __rebuildIterationsTable: function() {
      if (this.__iterationsTable) {
        this.__iterationsSection.remove(this.__iterationsTable);
      }

      const iterationsTable = this.__iterationsTable = new osparc.component.snapshots.Iterations(this.__study.serialize());
      iterationsTable.populateTable(this.__iterations);
      iterationsTable.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const iterationId = iterationsTable.getRowData(selectedRow)["Id"];
        this.__iterationSelected(iterationId);
      });

      this.__iterationsSection.addAt(iterationsTable, 0, {
        width: "60%"
      });
    },

    __buildIterationPreview: function() {
      const iterationPreview = this.__iterationPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.__iterationsSection.addAt(iterationPreview, 1, {
        width: "40%"
      });
    },

    __loadIterationPreview: function(iterationId) {
      const params = {
        url: {
          "studyId": this.__study.getUuid(),
          "snapshotId": iterationId
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
          this.__iterationPreview.set({
            study: study
          });
          this.__iterationPreview.loadModel(study.getWorkbench());
        });
    },

    __createOpenIterationBtn: function() {
      const openIterationBtn = new qx.ui.form.Button(this.tr("Open Iteration")).set({
        allowGrowX: false
      });
      return openIterationBtn;
    },

    __iterationSelected: function(iterationId) {
      this.__selectedIterationId = iterationId;

      if (this.__iterationsTable) {
        this.__iterationsTable.setSelection(iterationId);
      }

      this.__loadIterationPreview(iterationId);

      if (this.__openIterationBtn) {
        this.__openIterationBtn.setEnabled(true);
      }
    }
  }
});
