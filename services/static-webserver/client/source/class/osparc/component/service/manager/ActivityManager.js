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
    this.__createFetchingView();
    this.__createActionsBar();

    this.__reloadButton.fireEvent("execute");
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
    __fetchingView: null,
    __reloadButton: null,
    /**
     * Creates the top bar that holds the filtering widgets.
     */
    __createFiltersBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const filtersPart = new qx.ui.toolbar.Part();
      toolbar.add(filtersPart);

      const filtersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const nameFilter = new osparc.component.filter.TextFilter("name", "activityMonitor");
      const studyFilter = this.__studyFilter = new osparc.component.filter.StudyFilter("study", "activityMonitor");
      filtersContainer.add(nameFilter);
      filtersContainer.add(studyFilter);
      filtersPart.add(filtersContainer);

      this._add(toolbar);
      nameFilter.getChildControl("textfield").setPlaceholder(this.tr("Filter by name"));

      osparc.data.Resources.get("studies")
        .then(studies => studyFilter.buildMenu(studies));
    },

    /**
     * Creates the main view, holding an instance of {osparc.component.service.manager.ActivityTree}.
     */
    __createActivityTree: function() {
      this.__tree = new osparc.component.service.manager.ActivityTree();
      this._add(this.__tree, {
        flex: 1
      });
      this.__tree.addListener("treeUpdated", () => {
        osparc.data.Resources.get("studies")
          .then(studies => this.__studyFilter.buildMenu(studies));
      }, this);
    },

    /**
     * Creates a simple view with a fetching icon.
     */
    __createFetchingView: function() {
      this.__fetchingView = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignX: "center",
        alignY: "middle"
      })).set({
        visibility: "excluded"
      });
      const image = new qx.ui.basic.Image("@FontAwesome5Solid/circle-notch/26");
      image.getContentElement().addClass("rotate");
      this.__fetchingView.add(image);
      this._add(this.__fetchingView, {
        flex: 1
      });
    },

    /**
     * Creates the bottom bar, which has buttons to refresh the tree and execute different actions on selected items.
     */
    __createActionsBar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();
      const tablePart = new qx.ui.toolbar.Part();
      // const actionsPart = new qx.ui.toolbar.Part();
      toolbar.add(tablePart);
      // toolbar.addSpacer();
      // toolbar.add(actionsPart);

      const reloadButton = this.__reloadButton = new qx.ui.toolbar.Button(this.tr("Reload"), "@FontAwesome5Solid/sync-alt/14");
      tablePart.add(reloadButton);
      reloadButton.addListener("execute", () => {
        this.__tree.exclude();
        this.__fetchingView.show();
        this.__tree.reset().then(() => {
          this.__tree.show();
          this.__fetchingView.exclude();
        });
      }, this);

      /*
      const runButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/14");
      actionsPart.add(runButton);
      runButton.addListener("execute", () => osparc.FlashMessenger.getInstance().logAs("Not implemented"));

      const stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/14");
      actionsPart.add(stopButton);
      stopButton.addListener("execute", () => osparc.FlashMessenger.getInstance().logAs("Not implemented"));

      const infoButton = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info/14");
      actionsPart.add(infoButton);
      infoButton.addListener("execute", () => osparc.FlashMessenger.getInstance().logAs("Not implemented"));

      [runButton, stopButton, infoButton].map(button => this.__tree.bind("selected", button, "enabled", {
        converter: data => data.length > 0
      }));
      */

      this._add(toolbar);
    }
  }
});
