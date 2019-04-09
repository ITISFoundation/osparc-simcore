/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows the play/stop study button.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let controlsBar = new qxapp.desktop.ControlsBar();
 *   this.getRoot().add(controlsBar);
 * </pre>
 */

qx.Class.define("qxapp.desktop.ControlsBar", {
  extend: qx.ui.toolbar.ToolBar,

  construct: function() {
    this.base(arguments);

    this.setSpacing(10);
    this.setAppearance("sidepanel");

    this.__initDefault();

    this.setCanStart(true);
  },

  events: {
    "startPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __stopButton: null,
    __filterField: null,

    __initDefault: function() {
      const filterCtrls = new qx.ui.toolbar.Part();
      this.__filterField = new qxapp.component.filter.TextFilter("text", "workbench");
      filterCtrls.add(this.__filterField);
      this.add(filterCtrls);

      this.addSpacer();

      const simCtrls = new qx.ui.toolbar.Part();
      this.__startButton = this.__createStartButton();
      this.__stopButton = this.__createStopButton();
      const retrieveBtn = this.__createRetrieveButton();
      simCtrls.add(this.__startButton);
      simCtrls.add(this.__stopButton);
      simCtrls.add(retrieveBtn);
      this.add(simCtrls);
    },

    __createStartButton: function() {
      let startButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/16");

      startButton.addListener("execute", () => {
        this.fireEvent("startPipeline");
      }, this);

      return startButton;
    },

    __createStopButton: function() {
      let stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/16");

      stopButton.addListener("execute", () => {
        this.fireEvent("stopPipeline");
      }, this);
      return stopButton;
    },

    __createRetrieveButton: function() {
      let retrieveBtn = new qx.ui.toolbar.Button(this.tr("Retrieve"), "@FontAwesome5Solid/spinner/16");

      retrieveBtn.addListener("execute", () => {
        this.fireEvent("retrieveInputs");
      }, this);
      return retrieveBtn;
    },

    setCanStart: function(canStart) {
      this.__startButton.setVisibility(canStart ? "visible" : "excluded");
      this.__stopButton.setVisibility(canStart ? "excluded" : "visible");
    }
  }
});
