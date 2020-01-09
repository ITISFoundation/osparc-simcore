/* ************************************************************************

   osparc - the simcore frontend

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
 *   let controlsBar = new osparc.desktop.ControlsBar();
 *   this.getRoot().add(controlsBar);
 * </pre>
 */

qx.Class.define("osparc.desktop.ControlsBar", {
  extend: qx.ui.toolbar.ToolBar,

  construct: function() {
    this.base(arguments);

    this.setSpacing(10);
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

    __initDefault: function() {
      const filterCtrls = new qx.ui.toolbar.Part();
      const serviceFilters = new osparc.desktop.ServiceFilters("workbench");
      osparc.component.filter.UIFilterController.getInstance().registerContainer("workbench", serviceFilters);
      filterCtrls.add(serviceFilters);
      this.add(filterCtrls);

      this.addSpacer();

      const simCtrls = new qx.ui.toolbar.Part();
      const startButton = this.__startButton = this.__createStartButton();
      const stopButton = this.__stopButton = this.__createStopButton();
      simCtrls.add(startButton);
      simCtrls.add(stopButton);
      this.add(simCtrls);
    },

    __createStartButton: function() {
      const startButton = new qx.ui.toolbar.Button(this.tr("Run"), "@FontAwesome5Solid/play/14");
      osparc.utils.Utils.setIdToWidget(startButton, "runStudyBtn");
      startButton.addListener("execute", () => {
        this.fireEvent("startPipeline");
      }, this);

      return startButton;
    },

    __createStopButton: function() {
      const stopButton = new qx.ui.toolbar.Button(this.tr("Stop"), "@FontAwesome5Solid/stop-circle/14");

      stopButton.addListener("execute", () => {
        this.fireEvent("stopPipeline");
      }, this);
      return stopButton;
    }
  }
});
