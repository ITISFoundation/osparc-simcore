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
  extend: qx.ui.basic.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this.setAppearance("sidepanel");

    this.__initDefault();
  },

  events: {
    "startPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __stopButton: null,
    __pipelineCtrls: null,

    getStartButton: function() {
      return this.__startButton;
    },

    getStopButton: function() {
      return this.__stopButton;
    },

    __initDefault: function() {
      const stopButton = this.__createStopButton();
      stopButton.setEnabled(false);
      this._add(stopButton);

      const startButton = this.__createStartButton();
      this._.add(startButton);

      osparc.store.Store.getInstance().addListener("changeCurrentStudy", e => {
        const study = e.getData();
        this.__updateRunButtonsStatus(study);
      });
    },

    __updateRunButtonsStatus: function(study) {
      if (study) {
        const startButton = this.__startButton;
        const stopButton = this.__stopButton;
        if (study.getState() && study.getState().state) {
          const pipelineState = study.getState().state;
          switch (pipelineState.value) {
            case "PENDING":
            case "PUBLISHED":
            case "STARTED":
              startButton.setFetching(true);
              stopButton.setEnabled(true);
              break;
            case "NOT_STARTED":
            case "SUCCESS":
            case "FAILED":
            default:
              startButton.setFetching(false);
              stopButton.setEnabled(false);
              break;
          }
        }
        this.__pipelineCtrls.setVisibility(study.isReadOnly() ? "excluded" : "visible");
      }
    },

    __createStartButton: function() {
      const startButton = this.__startButton = this.__createButton(this.tr("Run"), "@FontAwesome5Solid/play/14", "runStudyBtn", "startPipeline");
      return startButton;
    },
    __createStopButton: function() {
      const stopButton = this.__stopButton = this.__createButton(this.tr("Stop"), "@FontAwesome5Solid/stop/14", "stopStudyBtn", "stopPipeline");
      return stopButton;
    },

    __createButton: function(label, icon, widgetId, signalName, visibility = "visible") {
      const button = new osparc.ui.toolbar.FetchButton(label, icon).set({
        visibility
      });
      osparc.utils.Utils.setIdToWidget(button, widgetId);
      button.addListener("execute", () => {
        this.fireEvent(signalName);
      }, this);
      return button;
    }
  }
});
