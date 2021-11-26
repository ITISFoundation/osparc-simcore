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
          runnableNodes.push(this.getStudy().getWorkbench().getNode(selectedNodeId));
        });
        const isSelectionRunnable = runnableNodes.length && runnableNodes.some(node => node && node.isComputational());
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
      const clustersSelectBox = this.__createClustersSelectBox();
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

    __createClustersSelectBox: function() {
      const selectBox = this.__clustersSelectBox = new qx.ui.form.SelectBox().set({
        alignY: "middle",
        maxHeight: 32
      });

      const store = osparc.store.Store.getInstance();
      store.addListener("changeClusters", () => this.__populateClustersSelectBox(), this);
      this.__populateClustersSelectBox();
      return selectBox;
    },

    __populateClustersSelectBox: function() {
      this.__clustersSelectBox.removeAll();

      const store = osparc.store.Store.getInstance();
      const clusters = store.getClusters();
      if (clusters) {
        const itemDefault = new qx.ui.form.ListItem().set({
          label: "default",
          toolTipText: "default cluster"
        });
        itemDefault.id = 0;
        this.__clustersSelectBox.add(itemDefault);
        clusters.forEach(cluster => {
          const item = new qx.ui.form.ListItem().set({
            label: cluster["name"],
            toolTipText: cluster["type"] + "\n" + cluster["description"],
            allowGrowY: false
          });
          item.id = cluster["id"];
          this.__clustersSelectBox.add(item);
        });
      }
      this.__clustersSelectBox.setVisibility(Object.keys(clusters).length ? "visible" : "excluded");
    },

    getClusterId: function() {
      if (this.__clustersSelectBox.isVisible()) {
        return this.__clustersSelectBox.getSelection()[0].id;
      }
      return null;
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
    },

    __checkButtonsVisible: function() {
      const allNodes = this.getStudy().getWorkbench().getNodes(true);
      const isRunnable = Object.values(allNodes).some(node => node.isComputational());
      this.__getStartButtons().forEach(startBtn => startBtn.setEnabled(isRunnable));

      const isReadOnly = this.getStudy().isReadOnly();
      this.setVisibility(isReadOnly ? "excluded" : "visible");
    },

    __updateRunButtonsStatus: function() {
      const study = this.getStudy();
      if (study) {
        const startButtons = this.__getStartButtons();
        const stopButton = this.__stopButton;
        const pipelineState = study.getPipelineState();
        if (pipelineState) {
          switch (pipelineState) {
            case "PENDING":
            case "PUBLISHED":
            case "STARTED":
              startButtons.forEach(startButton => startButton.setFetching(true));
              stopButton.setEnabled(true);
              break;
            case "NOT_STARTED":
            case "SUCCESS":
            case "FAILED":
            default:
              startButtons.forEach(startButton => startButton.setFetching(false));
              stopButton.setEnabled(false);
              break;
          }
        }
      }
    }
  }
});
