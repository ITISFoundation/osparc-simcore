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
      reloadButton.addListener("execute", () => this.__tree.update());

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
    }
  }
});
