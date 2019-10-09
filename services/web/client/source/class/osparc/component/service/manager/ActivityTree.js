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
      this.tr("Memory usage")
    ]);
    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });
    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setMinWidth(1, 80);
    columnModel.getBehavior().setMinWidth(2, 80);

    columnModel.setDataCellRenderer(4, new osparc.ui.table.cellrenderer.Percentage("#2c7cce"));
    columnModel.setDataCellRenderer(5, new osparc.ui.table.cellrenderer.Percentage("#358475"));

    this._applyMode(this.getMode());

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
      return Promise.all([osparc.data.Resources.get("studies"), osparc.data.Resources.getOne("activity")])
        .then(data => {
          const studies = data[0];
          const activity = data[1];
          console.log(studies, activity);
          const rows = [];
          studies.forEach(study => {
            let parentAdded = false;
            for (let key in study.workbench) {
              const node = study.workbench[key];
              if (Object.keys(activity).includes(key)) {
                if (this.getMode() !== this.self().modes.FLAT && !parentAdded) {
                  rows.push([
                    osparc.component.service.manager.ActivityManager.itemTypes.STUDY,
                    study.name,
                    "",
                    "",
                    -1,
                    -1
                  ]);
                  parentAdded = true;
                }
                const row = [];
                row[0] = osparc.component.service.manager.ActivityManager.itemTypes.SERVICE;
                row[1] = node.label;
                row[2] = activity[key].name;
                row[4] = Math.round(activity[key].stats.cpuUsage * 10) / 10;
                row[5] = Math.round(activity[key].stats.memoryUsage * 10) / 10;
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
      return this.update();
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
