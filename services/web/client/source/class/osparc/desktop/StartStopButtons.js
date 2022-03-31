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

    this.__initDefault();
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
    __startButton: null,
    __startSelectionButton: null,
    __startAllButton: null,
    __stopButton: null,

    setRunning: function(running) {
      this.__getStartButtons().forEach(startBtn => startBtn.setFetching(running));

      this.__stopButton.setEnabled(running);
    },

    nodeSelectionChanged: function(selectedNodeIds) {
      if (!this.__startButton.isFetching()) {
        const runnableNodes = [];
        selectedNodeIds.forEach(selectedNodeId => {
          if (this.getStudy()) {
            runnableNodes.push(this.getStudy().getWorkbench().getNode(selectedNodeId));
          }
        });
        const isSelectionRunnable = runnableNodes.length && runnableNodes.some(node => node && (node.isComputational() || node.isIterator()));
        if (isSelectionRunnable) {
          this.__startButton.exclude();
          this.__startSelectionButton.show();
        } else {
          this.__startButton.show();
          this.__startSelectionButton.exclude();
        }
      }
    },

    __getStartButtons: function() {
      return [
        this.__startButton,
        this.__startSelectionButton.getChildControl("button"),
        this.__startAllButton
      ];
    },

    __initDefault: function() {
      const clustersSelectBox = this.__createClustersLayout();
      this._add(clustersSelectBox);

      const startButton = this.__createStartButton();
      this._add(startButton);

      const startSplitButton = this.__createStartSplitButton().set({
        visibility: "excluded"
      });
      this._add(startSplitButton);

      const stopButton = this.__createStopButton();
      stopButton.setEnabled(false);
      this._add(stopButton);
    },

    __createClustersLayout: function() {
      const clustersLayout = this.__clustersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const selectBox = this.__clustersSelectBox = new qx.ui.form.SelectBox().set({
        alignY: "middle",
        maxHeight: 32
      });
      clustersLayout.add(selectBox);

      const store = osparc.store.Store.getInstance();
      store.addListener("changeClusters", () => this.__populateClustersSelectBox(), this);

      const clusterMiniView = new osparc.component.cluster.ClusterMiniView().set({
        alignY: "middle"
      });
      selectBox.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          clusterMiniView.setClusterId(selection[0].id);
        }
      }, this);
      clustersLayout.add(clusterMiniView);

      return clustersLayout;
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
      const clustersBox = this.__clustersSelectBox;
      if (clustersBox.isVisible()) {
        clustersBox.getSelectables().forEach(selectable => {
          if (selectable.id === clusterId) {
            clustersBox.setSelection([selectable]);
          }
        });
      }
    },

    __createStartButton: function() {
      const startButton = this.__startButton = new osparc.ui.toolbar.FetchButton(this.tr("Run"), "@FontAwesome5Solid/play/14");
      osparc.utils.Utils.setIdToWidget(startButton, "runStudyBtn");
      startButton.addListener("execute", () => this.fireEvent("startPipeline"), this);
      return startButton;
    },

    __createStartSplitButton: function() {
      const startSelectionButton = this.__startSelectionButton = new osparc.ui.toolbar.FetchSplitButton(this.tr("Run Selection"), "@FontAwesome5Solid/play/14");
      startSelectionButton.addListener("execute", () => this.fireEvent("startPartialPipeline"), this);
      const splitButtonMenu = this.__createSplitButtonMenu();
      startSelectionButton.setMenu(splitButtonMenu);
      return startSelectionButton;
    },

    __createSplitButtonMenu: function() {
      const splitButtonMenu = new qx.ui.menu.Menu();

      const startAllButton = this.__startAllButton = new osparc.ui.menu.FetchButton(this.tr("Run All"));
      startAllButton.addListener("execute", () => this.fireEvent("startPipeline"), this);
      splitButtonMenu.add(startAllButton);

      return splitButtonMenu;
    },

    __createStopButton: function() {
      const stopButton = this.__stopButton = new osparc.ui.toolbar.FetchButton(this.tr("Stop"), "@FontAwesome5Solid/stop/14");
      osparc.utils.Utils.setIdToWidget(stopButton, "stopStudyBtn");
      stopButton.addListener("execute", () => this.fireEvent("stopPipeline"), this);
      return stopButton;
    },

    __applyStudy: async function(study) {
      study.getWorkbench().addListener("pipelineChanged", this.__checkButtonsVisible, this);
      study.addListener("changeState", this.__updateRunButtonsStatus, this);
      this.__populateClustersSelectBox();
      this.__checkButtonsVisible();
      this.__getComputations();
    },

    __checkButtonsVisible: function() {
      const allNodes = this.getStudy().getWorkbench().getNodes(true);
      const isRunnable = Object.values(allNodes).some(node => (node.isComputational() || node.isIterator()));
      this.__getStartButtons().forEach(startBtn => {
        if (!startBtn.isFetching()) {
          startBtn.setEnabled(isRunnable);
        }
      }, this);

      const isReadOnly = this.getStudy().isReadOnly();
      this.setVisibility(isReadOnly ? "excluded" : "visible");
    },

    __updateRunButtonsStatus: function() {
      const study = this.getStudy();
      if (study) {
        this.setRunning(study.isPipelineRunning());
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
