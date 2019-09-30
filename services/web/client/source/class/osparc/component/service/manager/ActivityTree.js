/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a table display the status of running services in real time. Simulates, in some cases, the behavior of a tree.
 * Has sorting and resizing capabilities, and its UI changes depending on its display mode, that changes depending on the activated type of sorting.
 * WiP
 */
qx.Class.define("osparc.component.service.manager.ActivityTree", {
  extend: qx.ui.table.Table,

  /**
   * Constructor sets the model and general look.
   */
  construct: function(data) {
    this.__model = new qx.ui.table.model.Simple();
    this.__model.setColumns([
      this.tr("Type"),
      this.tr("Node"),
      this.tr("Service"),
      this.tr("Status"),
      this.tr("CPU usage"),
      this.tr("GPU usage")
    ]);
    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });
    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setMinWidth(1, 80);
    columnModel.getBehavior().setMinWidth(2, 80);

    this._applyMode(this.getMode());

    this.update();

    this.__attachEventHandlers();
  },

  properties: {
    mode: {
      check: "String",
      nullable: false,
      init: "hierarchical",
      apply: "_applyMode"
    },
    data: {
      check: "Array",
      apply: "_applyData"
    }
  },

  statics: {
    modes: {
      HIERARCHICAL: "hierarchical",
      FLAT: "flat"
    }
  },

  members: {
    __model: null,
    __filters: {},
    __sorting: {},

    _applyMode: function(mode) {
      const columnModel = this.getTableColumnModel();
      switch (mode) {
        case this.self().modes.HIERARCHICAL:
          columnModel.setDataCellRenderer(1,
            new qx.ui.table.cellrenderer.Dynamic(cellInfo => {
              if (cellInfo.rowData[0] === osparc.component.service.manager.ActivityManager.itemTypes.SERVICE) {
                return new osparc.ui.table.cellrenderer.Indented(1);
              }
              return new osparc.ui.table.cellrenderer.Indented(0);
            })
          );
          columnModel.setDataCellRenderer(4, new qx.ui.table.cellrenderer.Html("center"));
          columnModel.setDataCellRenderer(5, new qx.ui.table.cellrenderer.Html("center"));
          break;
        case this.self().modes.FLAT:
          columnModel.setDataCellRenderer(1, new qx.ui.table.cellrenderer.Default());
          break;
      }
    },

    _applyFilters: function(filters) {
      this.__filters = filters;
      const filterText = filters.name;
      const filterStudy = filters.study;
      // Filtering function
      const filter = row => {
        // By text
        const nameFilterFn = roww => {
          if (roww[0] === osparc.component.service.manager.ActivityManager.itemTypes.STUDY) {
            return true;
          }
          const name = roww[1];
          if (filterText.length > 1) {
            return name.trim().toLowerCase()
              .includes(filterText.trim().toLowerCase());
          }
          return true;
        };
        // By study
        const studyFilterFn = roww => {
          return true;
        };
        // Compose functions (AND)
        return nameFilterFn(row) && studyFilterFn(row);
      };
      // Apply filters
      const filteredData = this.getData().filter(row => filter(row));
      this.getTableModel().setData(this.__removeEmptyStudies(filteredData), false);
      if (this.__hasActiveSorting()) {
        const {
          columnIndex,
          ascending
        } = this.__sorting;
        this.getTableModel().sortByColumn(columnIndex, ascending);
      }
    },

    __removeEmptyStudies: function(data) {
      return data.filter((item, index, array) => {
        if (item[0] === osparc.component.service.manager.ActivityManager.itemTypes.STUDY) {
          if (index === array.length-1) {
            return false;
          }
          if (item[0] === array[index+1][0]) {
            return false;
          }
        }
        return true;
      });
    },

    __removeStudies(data) {
      return data.filter(item => item[0] !== osparc.component.service.manager.ActivityManager.itemTypes.STUDY);
    },

    _applyData: function(data) {
      this.getTableModel().setData(data, false);
    },

    /**
     * This functions updates the tree with the most recent data.
     */
    update: function() {
      osparc.data.Resources.get("studies")
        .then(studies => {
          const rows = [];
          studies.forEach(study => {
            let parentAdded = false;
            for (let key in study.workbench) {
              const node = study.workbench[key];
              const metadata = osparc.utils.Services.getNodeMetaData(node.key, node.version);
              if (metadata && metadata.type === "computational") {
                if (this.getMode() !== this.self().modes.FLAT && !parentAdded) {
                  rows.push([osparc.component.service.manager.ActivityManager.itemTypes.STUDY, study.name]);
                  parentAdded = true;
                }
                const row = [];
                row[0] = osparc.component.service.manager.ActivityManager.itemTypes.SERVICE;
                row[1] = node.label;
                if (metadata.key && metadata.key.length) {
                  const splitted = metadata.key.split("/");
                  row[2] = splitted[splitted.length-1];
                }
                const percentage = Math.floor(Math.random()*101);
                const percentageGpu = Math.floor(Math.random()*101);
                row[4] = "" +
                  `<div style="position: absolute; left: 0; right: 0;">${percentage}%</div>` +
                  `<div style="height: 100%; width: ${percentage}%; background-color: #2c7cce;"></div>`;
                row[5] = "" +
                  `<div style="position: absolute; left: 0; right: 0;">${percentageGpu}%</div>` +
                  `<div style="height: 100%; width: ${percentageGpu}%; background-color: #358475;"></div>`;
                rows.push(row);
              }
            }
          });
          this.setData(rows);
          if (this.__hasActiveFilters()) {
            this._applyFilters(this.__filters);
          }
          if (this.__hasActiveSorting()) {
            const {
              columnIndex,
              ascending
            } = this.__sorting;
            this.__model.sortByColumn(columnIndex, ascending);
          }
        })
        .catch(e => {
          console.error(e);
        });
    },

    __hasActiveFilters: function() {
      if (this.__filters.name && this.__filters.name.length) {
        return true;
      }
      if (this.__filters.service && this.__filters.service.length) {
        return true;
      }
      return false;
    },

    __hasActiveSorting: function() {
      if (Object.keys(this.__sorting).length) {
        return true;
      }
      return false;
    },

    reset: function() {
      this.__sorting = {};
      this.getTableModel().clearSorting();
      this.setMode(this.self().modes.HIERARCHICAL);
      this.update();
    },

    __attachEventHandlers: function() {
      // React to filter changes
      const msgName = osparc.utils.Utils.capitalize("activityMonitor", "filter");
      qx.event.message.Bus.getInstance().subscribe(msgName, msg => this._applyFilters(msg.getData()), this);

      this.__model.addListener("sorted", e => {
        this.__sorting = e.getData();
        this.setMode(this.self().modes.FLAT);
        this.getTableModel().setData(this.__removeStudies(this.getTableModel().getData()), false);
      }, this);
    }
  }
});
