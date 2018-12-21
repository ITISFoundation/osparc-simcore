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
      layout: new qx.ui.layout.VBox(2),
      width: 600,
      zIndex: 1000
    });
  },

  members: {

    logAs: function(message, level="INFO", logger=null) {
      this.log({
        message: message,
        level: level.toUpperCase(),
        logger: logger
      });
    },

    log: function(logMessage) {
      let message = logMessage.message;
      const level = logMessage.level.toUpperCase(); // "DEBUG", "INFO", "WARNING", "ERROR"
      let logger =logMessage.logger;
      if (logger) {
        message = logger + ": " + message;
      }

      let label = new qx.ui.basic.Label(message).set({
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
          const left = Math.round((bounds.width - hint.width)/2);
          const top = 1;
          this.moveTo(left, top);
          return;
        }
      }
      this.center();
    }
  }
});
