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

    this._setLayout(new qx.ui.layout.HBox(5));

    this.setAppearance("sidepanel");

    this.__initDefault();
  },

  events: {
    "startPipeline": "qx.event.type.Event",
    "startPartialPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __startSelectionButton: null,
    __startAllButton: null,
    __stopButton: null,

    setRunning: function(running) {
      const startButtons = [this.__startButton, this.__startSelectionButton.getChildControl("button"), this.__startAllButton];
      startButtons.forEach(startButton => startButton.setFetching(running));
      this.__stopButton.setFetching(running);
    },

    nodeSelectionChanged: function(selectedNodes) {
      if (!this.__startButton.isFetching()) {
        if (selectedNodes.length) {
          this.__startButton.exclude();
          this.__startSelectionButton.show();
        } else {
          this.__startButton.show();
          this.__startSelectionButton.exclude();
        }
      }
    },

    __initDefault: function() {
      const stopButton = this.__createStopButton();
      stopButton.setEnabled(false);
      this._add(stopButton);

      const startButton = this.__createStartButton();
      this._add(startButton);

      const startSplitButton = this.__createStartSplitButton().set({
        visibility: "excluded"
      });
      this._add(startSplitButton);

      osparc.store.Store.getInstance().addListener("changeCurrentStudy", e => {
        const study = e.getData();
        this.__updateRunButtonsStatus(study);
      });
    },

    __updateRunButtonsStatus: function(study) {
      if (study) {
        const startButtons = [this.__startButton, this.__startSelectionButton.getChildControl("button"), this.__startAllButton];
        const stopButton = this.__stopButton;
        if (study.getState() && study.getState().state) {
          const pipelineState = study.getState().state;
          switch (pipelineState.value) {
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
    },

    __createStartButton: function() {
      const startButton = this.__startButton = new osparc.ui.toolbar.FetchButton(this.tr("Run"), "@FontAwesome5Solid/play/14");
      osparc.utils.Utils.setIdToWidget(startButton, "runStudyBtn");
      startButton.addListener("execute", () => {
        this.fireEvent("startPipeline");
      }, this);
      return startButton;
    },

    __createStartSplitButton: function() {
      const startSelectionButton = this.__startSelectionButton = new osparc.ui.toolbar.FetchSplitButton(this.tr("Run Node"), "@FontAwesome5Solid/play/14");
      startSelectionButton.addListener("execute", () => {
        this.fireEvent("startPartialPipeline");
      }, this);
      const splitButtonMenu = this.__createSplitButtonMenu();
      startSelectionButton.setMenu(splitButtonMenu);
      return startSelectionButton;
    },

    __createSplitButtonMenu: function() {
      const splitButtonMenu = new qx.ui.menu.Menu();

      const startAllButton = this.__startAllButton = new osparc.ui.menu.FetchButton(this.tr("Run All"));
      startAllButton.addListener("execute", () => {
        this.fireEvent("startPipeline");
      });
      splitButtonMenu.add(startAllButton);

      return splitButtonMenu;
    },

    __createStopButton: function() {
      const stopButton = this.__stopButton = new osparc.ui.toolbar.FetchButton(this.tr("Stop"), "@FontAwesome5Solid/stop/14");
      osparc.utils.Utils.setIdToWidget(stopButton, "stopStudyBtn");
      stopButton.addListener("execute", () => {
        this.fireEvent("stopPipeline");
      }, this);
      return stopButton;
    }
  }
});
