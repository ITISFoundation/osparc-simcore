qx.Class.define("qxapp.component.widget.FlashMessenger", {
  extend: qx.ui.window.Window,

  type: "singleton",

  construct: function() {
    this.base();

    this.set({
      appearance: "window-small-cap",
      showMinimize: false,
      showMaximize: false,
      allowMaximize: false,
      showStatusbar: false,
      resizable: false,
      contentPadding: 0,
      caption: "Logger",
      layout: new qx.ui.layout.VBox()
    });
  },

  members: {
    log: function(logMessage) {
      const message = logMessage.message;
      const level = logMessage.level; // "DEBUG", "INFO", "WARNING", "ERROR"
      const logger = logMessage.logger;

      let label = new qx.ui.basic.Label(logger + ": " + message).set({
        allowGrowX: true,
        allowGrowY: true,
        alignX: "center",
        textAlign: "center",
        padding: 5
      });
      this.add(label);

      switch (level) {
        case "DEBUG":
          label.setBackgroundColor("blue");
          label.setTextColor("white");
          break;
        case "INFO":
          label.setBackgroundColor("blue");
          label.setTextColor("white");
          break;
        case "WARNING":
          label.setBackgroundColor("yellow");
          label.setTextColor("black");
          break;
        case "ERROR":
          label.setBackgroundColor("red");
          label.setTextColor("black");
          break;
      }

      if (this.getVisibility() !== "visible") {
        this.__toTopCenter();
        this.open();
      }

      const time = 3000;
      qx.event.Timer.once(e => {
        this.remove(label);
        if (this.getChildren().length === 0) {
          this.close();
        }
      }, this, time);
    },

    __toTopCenter: function() {
      const parent = this.getLayoutParent();
      if (parent) {
        const bounds = parent.getBounds();
        if (bounds) {
          const hint = this.getSizeHint();
          const left = Math.round((bounds.width - hint.width) / 2);
          const top = 50;
          this.moveTo(left, top);
          return;
        }
      }
      this.center();
    }
  }
});
