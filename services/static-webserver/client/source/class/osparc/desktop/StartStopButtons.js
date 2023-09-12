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
 * Widget that shows the run and stop study button.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let startStopButtons = new osparc.desktop.StartStopButtons();
 *   this.getRoot().add(startStopButtons);
 * </pre>
 */

qx.Class.define("osparc.desktop.StartStopButtons", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();

    this.__attachEventHandlers();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  events: {
    "startPipeline": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __clustersLayout: null,
    __clustersSelectBox: null,
    __clusterMiniView: null,
    __dynamicsLayout: null,
    __startServiceButton: null,
    __stopServiceButton: null,
    __computationsLayout: null,
    __runButton: null,
    __runSelectionButton: null,
    __runAllButton: null,
    __stopButton: null,

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeNodeSelection", e => {
        const selectedNodes = e.getData();
        this.__nodeSelectionChanged(selectedNodes);
      }, this);
    },

    __nodeSelectionChanged: function(selectedNodes) {
      const isDynamic = selectedNodes.length === 1 && selectedNodes[0].isDynamic();
      this.__dynamicsLayout.setVisibility(isDynamic ? "visible" : "excluded");
      this.__computationsLayout.setVisibility(isDynamic ? "excluded" : "visible");

      // dynamics
      if (isDynamic) {
        const node = selectedNodes[0];

        const startButton = this.__startServiceButton;
        startButton.removeAllBindings();
        if ("executeListenerId" in startButton) {
          startButton.removeListenerById(startButton.executeListenerId);
        }
        node.attachHandlersToStartButton(startButton);

        const stopButton = this.__stopServiceButton;
        stopButton.removeAllBindings();
        if ("executeListenerId" in stopButton) {
          stopButton.removeListenerById(stopButton.executeListenerId);
        }
        node.attachVisibilityHandlerToStopButton(stopButton);
        node.attachExecuteHandlerToStopButton(stopButton);
      }

      // computationals
      if (!this.__runButton.isFetching()) {
        const isSelectionRunnable = selectedNodes.length && selectedNodes.some(node => node && (node.isComputational() || node.isIterator()));
        if (isSelectionRunnable) {
          this.__runButton.exclude();
          this.__runSelectionButton.show();
        } else {
          this.__runButton.show();
          this.__runSelectionButton.exclude();
        }
      }
    },

    __setRunning: function(running) {
      this.__getRunButtons().forEach(runBtn => runBtn.setFetching(running));

      this.__stopButton.setEnabled(running);
    },

    __getRunButtons: function() {
      return [
        this.__runButton,
        this.__runSelectionButton.getChildControl("button"),
        this.__runAllButton
      ];
    },

    __buildLayout: function() {
      const clustersLayout = this.__createClustersLayout();
      this._add(clustersLayout);

      const dynamicsLayout = this.__createDynamicsLayout().set({
        visibility: "excluded"
      });
      this._add(dynamicsLayout);

      const computationalsLayout = this.__createComputationalsLayout();
      this._add(computationalsLayout);
    },

    __createClustersLayout: function() {
      const clustersLayout = this.__clustersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));

      const selectBox = this.__clustersSelectBox = new qx.ui.form.SelectBox().set({
        maxHeight: 32
      });
      clustersLayout.add(selectBox);

      const store = osparc.store.Store.getInstance();
      store.addListener("changeClusters", () => this.__populateClustersSelectBox(), this);

      const clusterMiniView = this.__clusterMiniView = new osparc.cluster.ClusterMiniView();
      selectBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          clusterMiniView.setClusterId(selection[0].id);
        }
      }, this);
      clustersLayout.add(clusterMiniView);

      return clustersLayout;
    },

    __createDynamicsLayout: function() {
      const dynamicsLayout = this.__dynamicsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));

      const startServiceButton = this.__createStartServiceButton();
      dynamicsLayout.add(startServiceButton);

      const stopServiceButton = this.__createStopServiceButton();
      dynamicsLayout.add(stopServiceButton);

      return dynamicsLayout;
    },

    __createComputationalsLayout: function() {
      const computationsLayout = this.__computationsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));

      const runButton = this.__createRunButton();
      computationsLayout.add(runButton);

      const runSplitButton = this.__createRunSplitButton().set({
        visibility: "excluded"
      });
      computationsLayout.add(runSplitButton);

      const stopButton = this.__createStopButton();
      stopButton.setEnabled(false);
      computationsLayout.add(stopButton);

      return computationsLayout;
    },

    __populateClustersSelectBox: function() {
      const clusters = osparc.utils.Clusters.populateClustersSelectBox(this.__clustersSelectBox);
      this.__clustersLayout.setVisibility(Object.keys(clusters).length ? "visible" : "excluded");
    },

    getClusterId: function() {
      if (this.__clustersLayout.isVisible()) {
        return this.__clustersSelectBox.getSelection()[0].id;
      }
      return null;
    },

    __setClusterId: function(clusterId) {
      if (clusterId === null) {
        return;
      }
      const clustersBox = this.__clustersSelectBox;
      if (clustersBox.isVisible()) {
        clustersBox.getSelectables().forEach(selectable => {
          if (selectable.id === clusterId) {
            clustersBox.setSelection([selectable]);
          }
        });
      }
    },

    getClusterMiniView: function() {
      return this.__clusterMiniView;
    },

    __createStartServiceButton: function() {
      const startServiceButton = this.__startServiceButton = new qx.ui.toolbar.Button().set({
        label: this.tr("Start"),
        icon: "@FontAwesome5Solid/play/14"
      });
      return startServiceButton;
    },

    __createStopServiceButton: function() {
      const stopServiceButton = this.__stopServiceButton = new qx.ui.toolbar.Button().set({
        label: this.tr("Stop"),
        icon: "@FontAwesome5Solid/stop/14"
      });
      return stopServiceButton;
    },

    __createRunButton: function() {
      const runButton = this.__runButton = new osparc.ui.toolbar.FetchButton(this.tr("Run"), "@FontAwesome5Solid/play/14");
      osparc.utils.Utils.setIdToWidget(runButton, "runStudyBtn");
      runButton.addListener("execute", () => this.fireEvent("startPipeline"), this);
      return runButton;
    },

    __createRunSplitButton: function() {
      const runSelectionButton = this.__runSelectionButton = new osparc.ui.toolbar.FetchSplitButton(this.tr("Run Selection"), "@FontAwesome5Solid/play/14");
      runSelectionButton.addListener("execute", () => this.fireEvent("startPartialPipeline"), this);

      const runtAllButton = this.__runAllButton = new osparc.ui.menu.FetchButton(this.tr("Run All"));
      runtAllButton.addListener("execute", () => this.fireEvent("startPipeline"), this);
      const splitButtonMenu = new qx.ui.menu.Menu();
      splitButtonMenu.add(runtAllButton);
      runSelectionButton.setMenu(splitButtonMenu);

      return runSelectionButton;
    },

    __createStopButton: function() {
      const stopButton = this.__stopButton = new osparc.ui.toolbar.FetchButton(this.tr("Stop"), "@FontAwesome5Solid/stop/14");
      osparc.utils.Utils.setIdToWidget(stopButton, "stopStudyBtn");
      stopButton.addListener("execute", () => this.fireEvent("stopPipeline"), this);
      return stopButton;
    },

    __applyStudy: async function(study) {
      study.getWorkbench().addListener("pipelineChanged", this.__checkButtonsVisible, this);
      study.addListener("changePipelineRunning", this.__updateRunButtonsStatus, this);
      this.__populateClustersSelectBox();
      this.__checkButtonsVisible();
      this.__getComputations();
    },

    __checkButtonsVisible: function() {
      const allNodes = this.getStudy().getWorkbench().getNodes(true);
      const isRunnable = Object.values(allNodes).some(node => (node.isComputational() || node.isIterator()));
      this.__getRunButtons().forEach(runBtn => {
        if (!runBtn.isFetching()) {
          runBtn.setEnabled(isRunnable);
        }
      }, this);

      const isReadOnly = this.getStudy().isReadOnly();
      this.setVisibility(isReadOnly ? "excluded" : "visible");
    },

    __updateRunButtonsStatus: function() {
      const study = this.getStudy();
      if (study) {
        this.__setRunning(study.isPipelineRunning());
      }
    },

    __getComputations: function() {
      const studyId = this.getStudy().getUuid();
      const url = "/computations/" + encodeURIComponent(studyId);
      const req = new osparc.io.request.ApiRequest(url, "GET");
      req.addListener("success", e => {
        const res = e.getTarget().getResponse();
        if (res && res.data && "cluster_id" in res.data) {
          const clusterId = res.data["cluster_id"];
          this.__setClusterId(clusterId);
        }
      }, this);
      req.addListener("fail", e => {
        const res = e.getTarget().getResponse();
        if (res && res.error) {
          console.error(res.error);
        }
      });
      req.send();
    }
  }
});
