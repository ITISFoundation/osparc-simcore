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
qx.Class.define("osparc.component.service.manager.ActivityManager", {
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

  members: {
    __tree: null,
    __studyFilter: null,
    /**
     * Creates the top bar that holds the filtering widgets.
     */
    __createFiltersBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const filtersPart = new qx.ui.toolbar.Part();
      toolbar.add(filtersPart);

      const filtersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      const nameFilter = new osparc.component.filter.TextFilter("name", "activityMonitor");
      const studyFilter = this.__studyFilter = new osparc.component.filter.StudyFilter("study", "activityMonitor");
      const serviceFilter = new osparc.component.filter.ServiceFilter("service", "activityMonitor");
      filtersContainer.add(nameFilter);
      filtersContainer.add(studyFilter);
      filtersContainer.add(serviceFilter);
      filtersPart.add(filtersContainer);

      this._add(toolbar);
      nameFilter.getChildControl("textfield").setPlaceholder(this.tr("Filter by name"));

      // React to filter changes
      const msgName = osparc.utils.Utils.capitalize("activityMonitor", "filter");
      qx.event.message.Bus.getInstance().subscribe(msgName, msg => {
        const model = this.__tree.getDataModel();
        const filterText = msg.getData().name;
        const filterStudy = msg.getData().study;
        const filter = targetNode => {
          const nameFilterFn = node => {
            if (filterText && filterText.length) {
              if (node.type === qx.ui.treevirtual.MTreePrimitive.Type.BRANCH) {
                return true;
              } else if (node.label.indexOf(filterText) === -1) {
                return false;
              }
            }
            return true;
          };
          const studyFilterFn = node => {
            if (filterStudy && filterStudy.length) {
              if (node.type === qx.ui.treevirtual.MTreePrimitive.Type.LEAF) {
                return true;
              } else if (filterStudy.includes(node.label)) {
                return true;
              }
              return false;
            }
            return true;
          };
          return nameFilterFn(targetNode) && studyFilterFn(targetNode);
        };
        model.setFilter(filter);
      }, this);
    },

    /**
     * Creates the main view, holding an instance of {osparc.component.service.manager.ActivityTree}.
     */
    __createActivityTree: function() {
      const tree = this.__tree = new osparc.component.service.manager.ActivityTree();
      this._add(tree, {
        flex: 1
      });
    },

    /**
     * Creates the bottom bar, which has buttons to refresh the tree and execute different actions on selected items.
     */
    __createActionsBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const actionsPart = new qx.ui.toolbar.Part();
      toolbar.addSpacer();
      toolbar.add(actionsPart);

      const runButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/14");
      actionsPart.add(runButton);

      const stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/14");
      actionsPart.add(stopButton);

      const infoButton = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info/14");
      actionsPart.add(infoButton);

      this._add(toolbar);
    },

    /**
     * This functions updates the tree with the most recent data.
     */
    __updateTree: function() {
      const call = osparc.data.Resources.get("studies");
      call.then(studies => {
        const model = this.__tree.getDataModel();
        model.clearData();
        studies.forEach(study => {
          let parent = null;
          for (let key in study.workbench) {
            const node = study.workbench[key];
            const metadata = osparc.utils.Services.getNodeMetaData(node.key, node.version);
            if (metadata && metadata.type === "computational") {
              if (parent === null) {
                parent = model.addBranch(null, study.name, true);
              }
              const rowId = model.addLeaf(parent, node.label);
              if (metadata.key && metadata.key.length) {
                const splitted = metadata.key.split("/");
                model.setColumnData(rowId, 1, splitted[splitted.length-1]);
              }
            }
          }
        });
        model.setData();
        this.__studyFilter.buildMenu(studies);
      }).catch(e => {
        console.error(e);
      });
    }
  }
});
