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
    __loadingTable: null,
    __iterationsTable: null,
    __iterationPreview: null,
    __openIterationBtn: null,
    __selectedIterationId: null,

    __buildLayout: function() {
      const iterationsSection = this.__iterationsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(iterationsSection, {
        flex: 1
      });
      this.__buildIterations();
      this.__buildIterationsPreview();

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

    __buildIterations: function() {
      const loadingTable = this.__loadingTable = new osparc.component.snapshots.Loading(this.tr("iterations"));
      this.__iterationsSection.addAt(loadingTable, 0, {
        width: "50%"
      });

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
                this.__listenToNodeUpdates();
                this.__rebuildIterationsTable();
              });
          }
        });
    },

    __listenToNodeUpdates: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const slotName = "nodeUpdated";
      socket.on(slotName, data => {
        const dataUpdate = JSON.parse(data);
        const idx = this.__iterations.findIndex(it => it["uuid"] === dataUpdate["project_id"]);
        if (idx === -1) {
          return;
        }
        this.__iterationUpdated(dataUpdate);
      }, this);
    },

    __iterationUpdated: function(dataUpdate) {
      const idx = this.__iterations.findIndex(it => it["uuid"] === dataUpdate["project_id"]);
      if (idx === -1) {
        return;
      }

      const iterationData = this.__iterations[idx];
      const iteration = new osparc.data.model.Study(iterationData);
      iteration.buildWorkbench();
      iteration.setReadOnly(true);
      iteration.nodeUpdated(dataUpdate);

      if (this.__selectedIterationId === iteration.getUuid()) {
        this.__iterationPreview.set({
          study: iteration
        });
        this.__iterationPreview.loadModel(iteration.getWorkbench());
      }

      const iterationDataUpdated = iteration.serialize(false);
      this.__iterations.splice(idx, 1, iterationDataUpdated);
      this.__iterationsTable.iterationsToTable(this.__iterations);
    },

    __rebuildIterationsTable: function() {
      if (this.__loadingTable) {
        this.__iterationsSection.remove(this.__loadingTable);
        this.__loadingTable = null;
      }
      if (this.__iterationsTable) {
        this.__iterationsSection.remove(this.__iterationsTable);
      }

      const iterationsTable = this.__iterationsTable = new osparc.component.snapshots.Iterations(this.__study.serialize(false));
      iterationsTable.populateTable(this.__iterations);
      iterationsTable.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const iterationId = iterationsTable.getRowData(selectedRow)["uuid"];
        this.__iterationSelected(iterationId, {
          flex: 1
        });
      });

      this.__iterationsSection.addAt(iterationsTable, 0, {
        width: "50%"
      });
    },

    __buildIterationsPreview: function() {
      const iterationsPreview = this.__iterationPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.__iterationsSection.addAt(iterationsPreview, 1, {
        width: "50%"
      });
    },

    __reloadIteration: function(iterationId) {
      const params = {
        url: {
          "studyId": iterationId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(data => {
          const studyData = this.__study.serialize();
          studyData["workbench"] = data["workbench"];
          studyData["ui"] = data["ui"];

          const idx = this.__iterations.findIndex(it => it["uuid"] === data["uuid"]);
          if (idx !== -1) {
            this.__iterations.splice(idx, 1, data);
            this.__iterationsTable.iterationsToTable(this.__iterations);
          }

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

      this.__reloadIteration(iterationId);

      if (this.__openIterationBtn) {
        this.__openIterationBtn.setEnabled(true);
      }
    },

    unlistenToNodeUpdates: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const slotName = "nodeUpdated";
      socket.removeSlot(slotName);
    }
  }
});
