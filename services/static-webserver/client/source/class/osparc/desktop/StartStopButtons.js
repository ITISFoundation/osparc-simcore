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

    this.__nodeSelectionChanged([]);
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
    __runSelectionButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "cluster-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "cluster-selector": {
          control = new qx.ui.form.SelectBox().set({
            maxHeight: 32
          });
          this.getChildControl("cluster-layout").add(control);
          const store = osparc.store.Store.getInstance();
          store.addListener("changeClusters", () => this.__populateClustersSelectBox(), this);
          break;
        }
        case "cluster-mini-view":
          control = new osparc.cluster.ClusterMiniView();
          this.getChildControl("cluster-layout").add(control);
          this.getChildControl("cluster-selector").addListener("changeSelection", e => {
            const selection = e.getData();
            if (selection.length) {
              control.setClusterId(selection[0].id);
            }
          }, this);
          break;
        case "dynamics-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "start-service-button":
          control = new qx.ui.toolbar.Button().set({
            label: this.tr("Start"),
            icon: "@FontAwesome5Solid/play/14"
          });
          this.getChildControl("dynamics-layout").add(control);
          break;
        case "stop-service-button":
          control = new qx.ui.toolbar.Button().set({
            label: this.tr("Stop"),
            icon: "@FontAwesome5Solid/stop/14"
          });
          this.getChildControl("dynamics-layout").add(control);
          break;
        case "computationals-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._add(control);
          break;
        case "run-button":
          control = new osparc.ui.toolbar.FetchButton(this.tr("Run"), "@FontAwesome5Solid/play/14");
          osparc.utils.Utils.setIdToWidget(control, "runStudyBtn");
          control.addListener("execute", () => this.fireEvent("startPipeline"), this);
          this.getChildControl("computationals-layout").add(control);
          break;
        case "run-all-button": {
          control = new osparc.ui.menu.FetchButton(this.tr("Run All"));
          control.addListener("execute", () => this.fireEvent("startPipeline"), this);
          const splitButtonMenu = new qx.ui.menu.Menu();
          splitButtonMenu.add(control);
          this.__runSelectionButton.setMenu(splitButtonMenu);
          break;
        }
        case "stop-button":
          control = new osparc.ui.toolbar.FetchButton(this.tr("Stop"), "@FontAwesome5Solid/stop/14");
          osparc.utils.Utils.setIdToWidget(control, "stopStudyBtn");
          control.addListener("execute", () => this.fireEvent("stopPipeline"), this);
          this.getChildControl("computationals-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("cluster-selector");
      this.getChildControl("cluster-mini-view");

      this.getChildControl("start-service-button");
      this.getChildControl("stop-service-button");

      this.getChildControl("run-button");
      const runSelectionButton = this.__runSelectionButton = new osparc.ui.toolbar.FetchSplitButton(this.tr("Run Selection"), "@FontAwesome5Solid/play/14");
      runSelectionButton.addListener("execute", () => this.fireEvent("startPartialPipeline"), this);
      this.getChildControl("computationals-layout").add(runSelectionButton);
      this.getChildControl("run-all-button");
      this.getChildControl("stop-button");
    },

    __attachEventHandlers: function() {
      qx.event.message.Bus.subscribe("changeNodeSelection", e => {
        const selectedNodes = e.getData();
        this.__nodeSelectionChanged(selectedNodes);
      }, this);
    },

    __nodeSelectionChanged: function(selectedNodes) {
      const dynamicsLayout = this.getChildControl("dynamics-layout");
      const computationalsLayout = this.getChildControl("computationals-layout");
      if (selectedNodes.length === 1 && selectedNodes[0].isDynamic()) {
        // dynamic
        dynamicsLayout.show();
        computationalsLayout.exclude();

        const node = selectedNodes[0];

        const startButton = this.getChildControl("start-service-button");
        startButton.removeAllBindings();
        if ("executeListenerId" in startButton) {
          startButton.removeListenerById(startButton.executeListenerId);
        }
        node.attachHandlersToStartButton(startButton);

        const stopButton = this.getChildControl("stop-service-button");
        stopButton.removeAllBindings();
        if ("executeListenerId" in stopButton) {
          stopButton.removeListenerById(stopButton.executeListenerId);
        }
        node.attachVisibilityHandlerToStopButton(stopButton);
        node.attachExecuteHandlerToStopButton(stopButton);
      } else {
        // computationals and default
        dynamicsLayout.exclude();
        computationalsLayout.show();

        const isSelectionRunnable = selectedNodes.length && selectedNodes.some(node => node && (node.isComputational() || node.isIterator()));
        this.getChildControl("run-button").setVisibility(isSelectionRunnable ? "excluded" : "visible");
        this.__runSelectionButton.setVisibility(isSelectionRunnable ? "visible" : "excluded");
        this.getChildControl("run-all-button").setVisibility(isSelectionRunnable ? "visible" : "excluded");
      }
    },

    __setRunning: function(running) {
      this.__getRunButtons().forEach(runBtn => runBtn.setFetching(running));
      this.getChildControl("stop-button").setEnabled(running);
    },

    __getRunButtons: function() {
      return [
        this.getChildControl("run-button"),
        this.__runSelectionButton.getChildControl("button"),
        this.getChildControl("run-all-button")
      ];
    },

    __populateClustersSelectBox: function() {
      osparc.cluster.Utils.populateClustersSelectBox(this.getChildControl("cluster-selector"));
      const clusters = osparc.store.Store.getInstance().getClusters();
      this.getChildControl("cluster-layout").setVisibility(Object.keys(clusters).length ? "visible" : "excluded");
    },

    getClusterId: function() {
      if (this.getChildControl("cluster-layout").isVisible()) {
        return this.getChildControl("cluster-selector").getSelection()[0].id;
      }
      return null;
    },

    __applyStudy: async function(study) {
      study.getWorkbench().addListener("pipelineChanged", this.__checkButtonsVisible, this);
      study.addListener("changePipelineRunning", this.__updateRunButtonsStatus, this);
      this.__populateClustersSelectBox();
      this.__getComputations();
      this.__checkButtonsVisible();
      this.__updateRunButtonsStatus();
    },

    __checkButtonsVisible: function() {
      const allNodes = this.getStudy().getWorkbench().getNodes();
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
          if (clusterId) {
            const clustersBox = this.getChildControl("cluster-selector");
            if (clustersBox.isVisible()) {
              clustersBox.getSelectables().forEach(selectable => {
                if (selectable.id === clusterId) {
                  clustersBox.setSelection([selectable]);
                }
              });
            }
          }
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
