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

qx.Class.define("osparc.snapshots.Iterations", {
  extend: osparc.ui.table.Table,

  construct: function(metaStudy) {
    this.__metaStudy = metaStudy;
    const model = this.__initModel();

    this.base(arguments, model, {
      initiallyHiddenColumns: [
        this.self().T_POS.ID.col
      ],
      statusBarVisible: false
    });

    this.setColumnWidth(this.self().T_POS.NAME.col, 150);
    this.setColumnWidth(this.self().T_POS.PROGRESS.col, 70);
  },

  statics: {
    T_POS: {
      ID: {
        col: 0,
        label: "uuid"
      },
      NAME: {
        col: 1,
        label: qx.locale.Manager.tr("Name")
      },
      PROGRESS: {
        col: 2,
        label: qx.locale.Manager.tr("Progress")
      }
    },

    extractIterators: function(iteration) {
      const iterators = [];
      Object.values(iteration["workbench"]).forEach(node => {
        if (osparc.data.model.Node.isIterator(node)) {
          iterators.push(node);
        }
      });
      return iterators;
    },

    extractProbes: function(iteration) {
      const probes = [];
      Object.values(iteration["workbench"]).forEach(node => {
        if (osparc.data.model.Node.isProbe(node)) {
          probes.push(node);
        }
      });
      return probes;
    },

    extractIteratorOutput: function(iterator) {
      if ("outputs" in iterator && "out_1" in iterator["outputs"]) {
        return iterator["outputs"]["out_1"];
      }
      return null;
    },

    extractProbeOutput: function(iteration, probe) {
      let nodeUuid = null;
      let portKey = null;
      if ("inputs" in probe && "in_1" in probe["inputs"]) {
        const input = probe["inputs"]["in_1"];
        nodeUuid = input["nodeUuid"];
        portKey = input["output"];
      }
      const itWB = iteration["workbench"];
      if (nodeUuid && nodeUuid in itWB &&
        "outputs" in itWB[nodeUuid] &&
        portKey && portKey in itWB[nodeUuid]["outputs"]) {
        return itWB[nodeUuid]["outputs"][portKey];
      }
      return null;
    }
  },

  members: {
    __metaStudy: null,

    getRowData: function(rowIdx) {
      return this.getTableModel().getRowDataAsMap(rowIdx);
    },

    __initModel: function() {
      const model = new qx.ui.table.model.Simple();

      const cols = [];
      Object.keys(this.self().T_POS).forEach(colKey => {
        const idx = this.self().T_POS[colKey].col;
        const label = this.self().T_POS[colKey].label;
        cols.splice(idx, 0, label);
      });

      const iteratorsInMeta = this.self().extractIterators(this.__metaStudy);
      iteratorsInMeta.forEach(iteratorInMeta => cols.push(iteratorInMeta["label"]));

      const probesInMeta = this.self().extractProbes(this.__metaStudy);
      probesInMeta.forEach(probeInMeta => cols.push(probeInMeta["label"]));

      model.setColumns(cols);

      return model;
    },

    populateTable: function(iterations) {
      if (iterations.length === 0) {
        return;
      }

      const iteratorsInMeta = this.self().extractIterators(iterations[0]);
      const probesInMeta = this.self().extractProbes(iterations[0]);

      const columnModel = this.getTableColumnModel();
      columnModel.setDataCellRenderer(this.self().T_POS.ID.col, new qx.ui.table.cellrenderer.Number());
      columnModel.setDataCellRenderer(this.self().T_POS.NAME.col, new qx.ui.table.cellrenderer.String());
      columnModel.setDataCellRenderer(this.self().T_POS.PROGRESS.col, new qx.ui.table.cellrenderer.String());
      let countFormat = this.self().T_POS.PROGRESS.col+1;
      iteratorsInMeta.forEach(() => {
        columnModel.setDataCellRenderer(countFormat, new qx.ui.table.cellrenderer.String());
        countFormat++;
      });
      probesInMeta.forEach(() => {
        columnModel.setDataCellRenderer(countFormat, new qx.ui.table.cellrenderer.String());
        countFormat++;
      });

      this.iterationsToTable(iterations);
    },

    iterationsToTable(iterations) {
      const rows = [];
      iterations.forEach(iteration => {
        const iterators = this.self().extractIterators(iteration);
        const probes = this.self().extractProbes(iteration);
        const row = [];
        row[this.self().T_POS.ID.col] = iteration["uuid"];
        row[this.self().T_POS.NAME.col] = iteration["name"];
        const studyProgress = osparc.data.model.Study.computeStudyProgress(iteration);
        row[this.self().T_POS.PROGRESS.col] = Math.floor(studyProgress)+"%";
        let countRow = this.self().T_POS.PROGRESS.col+1;
        iterators.forEach(iterator => {
          const itOut = this.self().extractIteratorOutput(iterator);
          if (itOut === null) {
            row[countRow] = "unknown";
          } else {
            row[countRow] = itOut.toString();
          }
          countRow++;
        });
        probes.forEach(probe => {
          const porbeOut = this.self().extractProbeOutput(iteration, probe);
          if (porbeOut === null) {
            row[countRow] = "unknown";
          } else {
            row[countRow] = porbeOut.toString();
          }
          countRow++;
        });
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    }
  }
});
