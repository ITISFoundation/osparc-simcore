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

qx.Class.define("qxapp.desktop.mainPanel.ControlsBar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    let leftBox = new qx.ui.layout.HBox(10, "left");
    this.__leftSide = new qx.ui.container.Composite(leftBox);
    this._add(this.__leftSide, {
      width: "50%"
    });

    let rightBox = new qx.ui.layout.HBox(10, "right");
    this.__rightSide = new qx.ui.container.Composite(rightBox);
    this._add(this.__rightSide, {
      width: "50%"
    });

    this.__initDefault();

    this.setCanStart(true);
  },

  events: {
    "startPipeline": "qx.event.type.Event",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __stopButton: null,

    __initDefault: function() {
      let playBtn = this.__startButton = this.__createStartButton();
      let stopButton = this.__stopButton = this.__createStopButton();
      this.__rightSide.add(playBtn);
      this.__rightSide.add(stopButton);
    },

    __createStartButton: function() {
      let startButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/play/32"
      });

      startButton.addListener("execute", function() {
        this.fireEvent("startPipeline");
      }, this);

      return startButton;
    },

    __createStopButton: function() {
      let stopButton = this.__stopButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/stop-circle/32"
      });

      stopButton.addListener("execute", function() {
        this.fireEvent("stopPipeline");
      }, this);
      return stopButton;
    },

    setCanStart: function(value) {
      if (value) {
        this.__startButton.setVisibility("visible");
        this.__stopButton.setVisibility("excluded");
      } else {
        this.__startButton.setVisibility("excluded");
        this.__stopButton.setVisibility("visible");
      }
    }
  }
});
