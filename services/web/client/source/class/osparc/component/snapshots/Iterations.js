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

qx.Class.define("osparc.component.snapshots.Iterations", {
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

    this.setColumnWidth(this.self().T_POS.NAME.col, 200);
  },

  statics: {
    T_POS: {
      ID: {
        col: 0,
        label: "Id"
      },
      NAME: {
        col: 1,
        label: qx.locale.Manager.tr("Name")
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

    extractProbeOutput: function(probe) {
      console.log("extractProbeOutput", probe);
      return 4;
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

    setSelection: function(iterationId) {
      this.resetSelection();
      for (let i=0; i<this.getTableModel().getRowCount(); i++) {
        if (this.getRowData(i)["Id"] === iterationId) {
          this.getSelectionModel().setSelectionInterval(i, i);
          return;
        }
      }
    },

    populateTable: function(iterations) {
      if (iterations.length === 0) {
        return;
      }

      console.log("populateTable", iterations);
      const iteratorsInMeta = this.self().extractIterators(iterations[0]);
      const probesInMeta = this.self().extractProbes(iterations[0]);

      const columnModel = this.getTableColumnModel();
      columnModel.setDataCellRenderer(this.self().T_POS.ID.col, new qx.ui.table.cellrenderer.Number());
      columnModel.setDataCellRenderer(this.self().T_POS.NAME.col, new qx.ui.table.cellrenderer.String());
      let countFormat = this.self().T_POS.NAME.col+1;
      iteratorsInMeta.forEach(() => {
        columnModel.setDataCellRenderer(countFormat, new qx.ui.table.cellrenderer.String());
        countFormat++;
      });
      probesInMeta.forEach(() => {
        columnModel.setDataCellRenderer(countFormat, new qx.ui.table.cellrenderer.String());
        countFormat++;
      });

      const rows = [];
      iterations.forEach(iteration => {
        const iterators = this.self().extractIterators(iteration);
        const probes = this.self().extractProbes(iteration);
        const row = [];
        row[this.self().T_POS.ID.col] = iteration["uuid"];
        row[this.self().T_POS.NAME.col] = iteration["name"];
        let countRow = this.self().T_POS.NAME.col+1;
        iterators.forEach(iterator => {
          const itOut = this.self().extractIteratorOutput(iterator);
          if (itOut) {
            row[countRow] = itOut.toString();
          } else {
            row[countRow] = "unknown";
          }
          countRow++;
        });
        probes.forEach(probe => {
          const porbeOut = this.self().extractProbeOutput(probe);
          if (porbeOut) {
            row[countRow] = porbeOut.toString();
          } else {
            row[countRow] = "unknown";
          }
          countRow++;
        });
        rows.push(row);
      });
      this.getTableModel().setData(rows, false);
    }
  }
});
