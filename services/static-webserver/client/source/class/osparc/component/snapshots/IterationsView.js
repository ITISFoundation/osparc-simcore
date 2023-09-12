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
  extend: qx.ui.splitpane.Pane,

  construct: function(study) {
    this.base(arguments, "horizontal");

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
    __tagIterationBtn: null,
    __deleteIterationBtn: null,
    __openIterationBtn: null,
    __selectedIterationId: null,
    // throttling
    __lastUpdate: null,
    __lastFunc: null,

    __buildLayout: function() {
      const iterationsSection = this.__iterationsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this.add(iterationsSection, 1);

      this.__buildIterations();
      this.__buildSnapshotButtons();

      const iterationsPreview = this.__iterationPreview = new osparc.component.workbench.WorkbenchUIPreview();
      this.add(iterationsPreview, 1);
    },

    __buildIterations: function() {
      const loadingTable = this.__loadingTable = new osparc.component.snapshots.Loading(this.tr("iterations"));
      this.__iterationsSection.addAt(loadingTable, 0, {
        flex: 1
      });

      this.__study.getIterations()
        .then(iterations => {
          if (iterations.length) {
            const iterationPromises = [];
            iterations.forEach(iteration => {
              const params = {
                url: {
                  "studyId": iteration["workcopy_project_id"]
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

    __buildSnapshotButtons: function() {
      const buttonsSection = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(buttonsSection);

      const tagIterationBtn = this.__tagIterationBtn = this.__createTagIterationBtn();
      tagIterationBtn.setEnabled(false);
      tagIterationBtn.addListener("execute", () => {
        if (this.__selectedIterationId) {
          this.__tagIteration(this.__selectedIterationId);
        }
      });
      buttonsSection.add(tagIterationBtn);

      const deleteIterationBtn = this.__deleteIterationBtn = this.__createDeleteIterationBtn();
      deleteIterationBtn.setEnabled(false);
      buttonsSection.add(deleteIterationBtn);

      const openIterationBtn = this.__openIterationBtn = this.__createOpenIterationBtn();
      openIterationBtn.setEnabled(false);
      openIterationBtn.addListener("execute", () => {
        if (this.__selectedIterationId) {
          this.fireDataEvent("openIteration", this.__selectedIterationId);
        }
      });
      buttonsSection.add(openIterationBtn);

      this.__iterationsSection.addAt(buttonsSection, 1);
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
      iteration.setReadOnly(true);
      iteration.nodeUpdated(dataUpdate);
      const iterationDataUpdated = iteration.serialize(false);
      this.__iterations.splice(idx, 1, iterationDataUpdated);

      // update maximum once every 2"
      const throttleTime = 2000;
      this.__throttleUpdate(this.__updateNewData.bind(this), throttleTime);
    },

    __throttleUpdate: function(callback, time) {
      if (this.__lastUpdate) {
        if (this.__lastFunc) {
          clearTimeout(this.__lastFunc);
        }
        this.__lastFunc = setTimeout(() => {
          if ((Date.now() - this.__lastUpdate) >= time) {
            callback();
            this.__lastUpdate = Date.now();
          }
        }, time - (Date.now() - this.__lastUpdate));
      } else {
        callback();
        this.__lastUpdate = Date.now();
      }
    },

    __updateNewData: function() {
      const idx = this.__iterations.findIndex(it => it["uuid"] === this.__selectedIterationId);
      if (idx > -1) {
        const iterationData = this.__iterations[idx];
        const iteration = new osparc.data.model.Study(iterationData);
        iteration.setReadOnly(true);
        this.__iterationPreview.setStudy(iteration);
        this.__iterationPreview.loadModel(iteration.getWorkbench());
      }

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
        this.__iterationSelected(iterationId);
      });

      this.__iterationsSection.addAt(iterationsTable, 0, {
        flex: 1
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
          study.setReadOnly(true);
          this.__iterationPreview.set({
            study: study
          });
          this.__iterationPreview.loadModel(study.getWorkbench());
        });
    },

    __createTagIterationBtn: function() {
      const tagIterationBtn = new qx.ui.form.Button(this.tr("Edit Tag")).set({
        allowGrowX: false,
        alignX: "left"
      });
      return tagIterationBtn;
    },

    __createDeleteIterationBtn: function() {
      const deleteIterationBtn = new qx.ui.form.Button(this.tr("Delete")).set({
        appearance: "danger-button",
        allowGrowX: false,
        alignX: "left"
      });
      return deleteIterationBtn;
    },

    __createOpenIterationBtn: function() {
      const openIterationBtn = new qx.ui.form.Button(this.tr("Open")).set({
        allowGrowX: false,
        alignX: "right"
      });
      return openIterationBtn;
    },

    __tagIteration: function(iterationId) {
      const selectedSnapshot = this.__iterations.find(iteration => iteration["uuid"] === iterationId);
      if (selectedSnapshot) {
        const editSnapshotView = new osparc.component.snapshots.EditSnapshotView();
        const tagCtrl = editSnapshotView.getChildControl("tags");
        tagCtrl.setValue(selectedSnapshot["tags"][0]);
        const msgCtrl = editSnapshotView.getChildControl("message");
        msgCtrl.setValue(selectedSnapshot["message"]);
        const title = this.tr("Edit Iteration");
        const win = osparc.ui.window.Window.popUpInWindow(editSnapshotView, title, 400, 180);
        editSnapshotView.addListener("takeSnapshot", () => {
          const params = {
            url: {
              "studyId": this.__study.getUuid(),
              "snapshotId": iterationId
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
            .catch(err => osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR"));
          win.close();
        }, this);
        editSnapshotView.addListener("cancel", () => {
          win.close();
        }, this);
      }
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
