/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * This is a sort of Task Manager or Activity Monitor for oSPARC. It provides the user with the status of the different services running
 * (queueing, hardware usage, running status, etc) and allows to run several actions on them.
 */
qx.Class.define("qxapp.component.service.manager.ActivityManager", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor builds the widget's interface.
   */
  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__createFiltersBar();
    this.__createActivityTree();
    this.__createActionsBar();

    this.__updateTree();
  },

  statics: {
    itemTypes: {
      STUDY: "study",
      SERVICE: "service"
    }
  },

  members: {
    __tree: null,
    __studyFilter: null,
    __data: null,

    /**
     * Creates the top bar that holds the filtering widgets.
     */
    __createFiltersBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const filtersPart = new qx.ui.toolbar.Part();
      toolbar.add(filtersPart);

      const filtersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const textFiltersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const nameFilter = new qxapp.component.filter.TextFilter("name", "activityMonitor");
      const studyFilter = this.__studyFilter = new qxapp.component.filter.StudyFilter("study", "activityMonitor");
      const serviceFilter = new qxapp.component.filter.ServiceFilter("service", "activityMonitor");
      textFiltersContainer.add(nameFilter);
      textFiltersContainer.add(serviceFilter);
      filtersContainer.add(textFiltersContainer);
      filtersContainer.add(studyFilter);
      filtersPart.add(filtersContainer);

      this._add(toolbar);
      nameFilter.getChildControl("textfield").setPlaceholder(this.tr("Filter by name"));

      // React to filter changes
      const msgName = qxapp.utils.Utils.capitalize("activityMonitor", "filter");
      qx.event.message.Bus.getInstance().subscribe(msgName, msg => this.__applyFilter(msg), this);
    },

    /**
     * Creates the main view, holding an instance of {qxapp.component.service.manager.ActivityTree}.
     */
    __createActivityTree: function() {
      this.__tree = new qxapp.component.service.manager.ActivityTree();
      this._add(this.__tree, {
        flex: 1
      });
    },

    /**
     * Creates the bottom bar, which has buttons to refresh the tree and execute different actions on selected items.
     */
    __createActionsBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const tablePart = new qx.ui.toolbar.Part();
      const actionsPart = new qx.ui.toolbar.Part();
      toolbar.add(tablePart);
      toolbar.addSpacer();
      toolbar.add(actionsPart);

      const reloadButton = new qx.ui.toolbar.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14");
      tablePart.add(reloadButton);
      reloadButton.addListener("execute", () => this.__updateTree(false));

      const runButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/14");
      actionsPart.add(runButton);
      runButton.addListener("execute", () => qxapp.component.message.FlashMessenger.getInstance().logAs("Not implemented"));

      const stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/14");
      actionsPart.add(stopButton);
      stopButton.addListener("execute", () => qxapp.component.message.FlashMessenger.getInstance().logAs("Not implemented"));

      const infoButton = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info/14");
      actionsPart.add(infoButton);
      infoButton.addListener("execute", () => qxapp.component.message.FlashMessenger.getInstance().logAs("Not implemented"));

      this._add(toolbar);
    },

    /**
     * This functions updates the tree with the most recent data.
     */
    __updateTree: function(useCache = true) {
      qxapp.data.Resources.get("studies", null, useCache)
        .then(studies => {
          const rows = [];
          studies.forEach(study => {
            let parentAdded = false;
            for (let key in study.workbench) {
              const node = study.workbench[key];
              const metadata = qxapp.utils.Services.getNodeMetaData(node.key, node.version);
              if (metadata && metadata.type === "computational") {
                if (!parentAdded) {
                  rows.push([this.self().itemTypes.STUDY, study.name]);
                  parentAdded = true;
                }
                const row = [];
                row[0] = this.self().itemTypes.SERVICE;
                row[1] = node.label;
                if (metadata.key && metadata.key.length) {
                  const splitted = metadata.key.split("/");
                  row[2] = splitted[splitted.length-1];
                }
                rows.push(row);
              }
            }
          });
          this.__tree.getTableModel().setData(rows, false);
          this.__studyFilter.buildMenu(studies);
          this.__data = rows;
        })
        .catch(e => {
          console.error(e);
        });
    },

    __applyFilter: function(msg) {
      const filterText = msg.getData().name;
      const filterStudy = msg.getData().study;
      const filter = row => {
        const nameFilterFn = roww => {
          const name = roww[0];
          if (filterText.length > 1) {
            return name.trim().toLowerCase()
              .includes(filterText.trim().toLowerCase());
          }
          return true;
        };
        const studyFilterFn = roww => {
          return true;
        };
        return nameFilterFn(row) && studyFilterFn(row);
      };
      const filteredData = this.__data.filter(row => filter(row));
      this.__tree.getTableModel().setData(filteredData);
    }
  }
});
