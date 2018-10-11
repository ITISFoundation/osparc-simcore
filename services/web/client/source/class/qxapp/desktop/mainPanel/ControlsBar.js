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
    "SavePressed": "qx.event.type.Event",
    "StartPipeline": "qx.event.type.Event",
    "StopPipeline": "qx.event.type.Event"
  },

  members: {
    __startButton: null,
    __stopButton: null,

    __initDefault: function() {
      let saveBtn = this.__createSaveButton();
      this.__rightSide.add(saveBtn);
      let playBtn = this.__startButton = this.__createStartButton();
      let stopButton = this.__stopButton = this.__createStopButton();
      this.__rightSide.add(playBtn);
      this.__rightSide.add(stopButton);
    },

    __createSaveButton: function() {
      let saveBtn = this.__saveButton = new qx.ui.form.Button();
      saveBtn.setIcon("@FontAwesome5Solid/save/32");
      saveBtn.addListener("execute", function() {
        this.fireEvent("SavePressed");
      }, this);
      return saveBtn;
    },

    __createStartButton: function() {
      let startButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/play/32"
      });

      startButton.addListener("execute", function() {
        this.fireEvent("StartPipeline");
      }, this);

      return startButton;
    },

    __createStopButton: function() {
      let stopButton = this.__stopButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/stop-circle/32"
      });

      stopButton.addListener("execute", function() {
        this.fireEvent("StopPipeline");
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
