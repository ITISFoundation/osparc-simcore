/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a table display the status of running services in real time. Simulates, in some cases, the behavior of a tree.
 * Has sorting and resizing capabilities, and its UI changes depending on its display mode, that changes depending on the activated type of sorting.
 */
qx.Class.define("osparc.activityManager.ActivityTree", {
  extend: osparc.ui.table.Table,

  /**
   * Constructor sets the model and general look.
   */
  construct: function() {
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

    columnModel.setDataCellRenderer(4, new osparc.ui.table.cellrenderer.Percentage("activitytree-background-cpu"));
    columnModel.setDataCellRenderer(5, new osparc.ui.table.cellrenderer.Percentage("activitytree-background-memory").set({
      unit: "MB"
    }));

    this.getSelectionModel().setSelectionMode(qx.ui.table.selection.Model.MULTIPLE_INTERVAL_SELECTION_TOGGLE);

    this._applyMode(this.getMode());

    this.__filters = {};
    this.__sorting = {};

    this.__attachEventHandlers();
  },

  properties: {
    mode: {
      check: "String",
      nullable: false,
      init: "hierarchical",
      apply: "_applyMode"
    },
    selected: {
      check: "Array",
      init: [],
      event: "changeSelection"
    },
    alwaysUpdate: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  statics: {
    modes: {
      HIERARCHICAL: "hierarchical",
      FLAT: "flat"
    }
  },

  events: {
    "treeUpdated": "qx.event.type.Event"
  },

  members: {
    __model: null,
    __filters: null,
    __sorting: null,
    __serviceNames: null,

    _applyMode: function(mode) {
      const columnModel = this.getTableColumnModel();
      switch (mode) {
        case this.self().modes.HIERARCHICAL:
          columnModel.setDataCellRenderer(1,
            new qx.ui.table.cellrenderer.Dynamic(cellInfo => {
              if (cellInfo.rowData[0] === osparc.activityManager.ActivityManager.itemTypes.SERVICE) {
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
      // By text
      const nameFilterFn = row => {
        if (row[0] === osparc.activityManager.ActivityManager.itemTypes.STUDY) {
          return true;
        }
        if (filterText && filterText.length > 1) {
          const trimmedText = filterText.trim().toLowerCase();
          return row[1].trim().toLowerCase()
            .includes(trimmedText) ||
            row[2].trim().toLowerCase()
              .includes(trimmedText);
        }
        return true;
      };
      const studyFilterFn = (row, index, array) => {
        if (row[0] === osparc.activityManager.ActivityManager.itemTypes.SERVICE) {
          return true;
        }
        if (filterStudy && filterStudy.length && !filterStudy.includes(row[1])) {
          // Remove also its services
          let i = index + 1;
          let next = array[i];
          while (next && next[0] === osparc.activityManager.ActivityManager.itemTypes.SERVICE && i < array.length) {
            array.splice(i, 1);
            next = array[i];
          }
          return false;
        }
        return true;
      };
      // Apply filters (working on a copy of the data)
      const filteredData = [...this.getData()].filter(studyFilterFn).filter(nameFilterFn);
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
        if (item[0] === osparc.activityManager.ActivityManager.itemTypes.STUDY) {
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

    __removeStudies: function(data) {
      return data.filter(item => item[0] !== osparc.activityManager.ActivityManager.itemTypes.STUDY);
    },

    /**
     * This functions updates the tree with the most recent data.
     */
    update: function() {
      return Promise.all([osparc.data.Resources.get("studies"), osparc.data.Resources.getOne("activity")])
        .then(async data => {
          const studies = data[0] || {};
          const activity = data[1] || {};

          // Get service names
          if (this.__serviceNames === null) {
            this.__serviceNames = await osparc.data.Resources.get("services");
          }

          const rows = [];
          studies.forEach(study => {
            let parentAdded = false;
            for (var key in study.workbench) {
              const node = study.workbench[key];
              if (this.getMode() !== this.self().modes.FLAT && !parentAdded) {
                rows.push([
                  osparc.activityManager.ActivityManager.itemTypes.STUDY,
                  study.name,
                  "",
                  "",
                  -1,
                  -1
                ]);
                parentAdded = true;
              }
              const row = [];
              // type
              row[0] = osparc.activityManager.ActivityManager.itemTypes.SERVICE;
              // given name
              row[1] = node.label;
              // original name
              if (this.__serviceNames[node.key]) {
                row[2] = this.__serviceNames[node.key];
              } else {
                const splitted = node.key.split("/");
                row[2] = splitted[splitted.length - 1];
              }
              if (Object.keys(activity).includes(key)) {
                const stats = activity[key].stats;
                const queued = activity[key].queued;
                const limits = activity[key].limits;
                if (stats) {
                  row[4] = stats.cpuUsage == null ? null : (Math.round(stats.cpuUsage * 10) / 10) + (limits && limits.cpus ? `/${limits.cpus * 100}` : "");
                  row[5] = stats.memUsage == null ? null : (Math.round(stats.memUsage * 10) / 10) + (limits && limits.mem ? `/${limits.mem}` : "");
                  row[3] = this.tr("Running");
                }
                if (queued) {
                  row[3] = this.tr("Queued");
                }
              } else {
                row[3] = this.tr("Not running");
              }
              rows.push(row);
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
          this.fireEvent("treeUpdated");
        })
        .catch(e => {
          console.error(e);
        })
        .then(() => {
          // Give a 2 seconds delay
          setTimeout(() => {
            if (this.getAlwaysUpdate()) {
              this.update();
            }
          }, 2000);
        });
    },

    __hasActiveFilters: function() {
      if (this.__filters.name && this.__filters.name.length) {
        return true;
      }
      if (this.__filters.study && this.__filters.study.length) {
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

      this.getSelectionModel().addListener("changeSelection", e => {
        this.setSelected(this.getSelection());
      }, this);

      this.addListener("disappear", () => {
        this.setAlwaysUpdate(false);
      }, this);
      this.addListener("appear", () => {
        this.resetAlwaysUpdate();
      }, this);
    }
  }
});
