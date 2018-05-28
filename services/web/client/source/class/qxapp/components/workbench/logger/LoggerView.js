/* eslint no-warning-comments: "off" */

const LOG_LEVEL = {
  debug: -1,
  info: 0,
  warning: 1,
  error: 2
};
Object.freeze(LOG_LEVEL);

qx.Class.define("qxapp.components.workbench.logger.LoggerView", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base();

    this.set({
      showMinimize: false,
      showStatusbar: false,
      width: 800,
      height: 300,
      caption: "Logger",
      layout: new qx.ui.layout.VBox(10)
    });

    // create the textfield
    let filterLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

    let clearButton = new qx.ui.form.Button("Clear");
    clearButton.addListener("execute", function(e) {
      this.__clearLogger();
    }, this);
    filterLayout.add(clearButton);

    let searchLabel = new qx.ui.basic.Label("Filter");
    filterLayout.add(searchLabel);
    let textfield = new qx.ui.form.TextField();
    textfield.setLiveUpdate(true);
    filterLayout.add(textfield, {
      flex: 1
    });

    let showDebugButton = new qx.ui.form.ToggleButton("Debug");
    showDebugButton.setValue(true);
    showDebugButton.addListener("changeValue", function(e) {
      this.__activeLogLevel = LOG_LEVEL.debug;
      console.log("show", this.__activeLogLevel);
    }, this);
    filterLayout.add(showDebugButton);

    let showInfoButton = new qx.ui.form.ToggleButton("Info");
    showInfoButton.setValue(true);
    showInfoButton.addListener("changeValue", function(e) {
      this.__activeLogLevel = LOG_LEVEL.info;
      console.log("show", this.__activeLogLevel);
    });
    filterLayout.add(showInfoButton);

    let showWarnButton = new qx.ui.form.ToggleButton("Warning");
    showWarnButton.setValue(true);
    showWarnButton.addListener("changeValue", function(e) {
      this.__activeLogLevel = LOG_LEVEL.warn;
      console.log("show", this.__activeLogLevel);
    });
    filterLayout.add(showWarnButton);

    let showErrorButton = new qx.ui.form.ToggleButton("Error");
    showErrorButton.setValue(true);
    showErrorButton.addListener("changeValue", function(e) {
      this.__activeLogLevel = LOG_LEVEL.error;
      console.log("show", this.__activeLogLevel);
    });
    filterLayout.add(showErrorButton);

    let group = new qx.ui.form.RadioGroup();
    group.add(showDebugButton, showInfoButton, showWarnButton, showErrorButton);

    this.add(filterLayout);

    let scroller = new qx.ui.container.Scroll();
    this.add(scroller, {
      flex: 1
    });

    this.__logList = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    scroller.add(this.__logList);

    this.__messengerColors = new Set();

    this.__logs = [];
    let initLog = this.__createInitMsg();
    this.__logs.push(initLog);

    textfield.addListener("changeValue", this.__filterString, this);
  },

  events: {},

  members: {
    __textArea: null,
    __logList: null,
    __messengerColors: null,
    __logs: null,
    __activeLogLevel: LOG_LEVEL.debug,

    addLog: function(what, who = "System", logLevel = LOG_LEVEL.info) {
      const whoRich = this.__addWhoColorTag(who);
      const whatRich = this.__addLevelColorTag(what, logLevel);
      const richMsg = whoRich + ": " + whatRich;
      let label = new qx.ui.basic.Label(richMsg).set({
        selectable: true,
        rich: true
      });
      label.who = who;
      label.what = what;
      label.logLevel = logLevel;
      this.__logList.add(label);
    },

    __addWhoColorTag: function(who) {
      let whoColor = null;
      for (let item of this.__messengerColors) {
        if (item[0] === who) {
          whoColor = item[1];
          break;
        }
      }
      if (whoColor === null) {
        whoColor = qxapp.utils.Utils.getRandomColor();
        this.__messengerColors.add([who, whoColor]);
      }

      return ("<font color=" + whoColor +">" + who + "</font>");
    },

    __addLevelColorTag: function(what, logLevel) {
      let logColor = null;

      switch (logLevel) {
        case LOG_LEVEL.debug:
          logColor = qxapp.theme.Color.colors["logger-debug-message"];
          break;
        case LOG_LEVEL.info:
          logColor = qxapp.theme.Color.colors["logger-info-message"];
          break;
        case LOG_LEVEL.warning:
          logColor = qxapp.theme.Color.colors["logger-warning-message"];
          break;
        case LOG_LEVEL.error:
          logColor = qxapp.theme.Color.colors["logger-error-message"];
          break;
        default:
          logColor = qxapp.theme.Color.colors["logger-info-message"];
          break;
      }

      return ("<font color=" + logColor +">" + what + "</font>");
    },

    __filterString: function(e) {
      const caseSensitive = false;
      let searchString = e.getData();
      if (caseSensitive === false) {
        searchString = searchString.toUpperCase();
      }
      for (let i=0; i<this.__logList.getChildren().length; i++) {
        let label = this.__logList.getChildren()[i];
        let msg = label.who + ": " + label.what;
        if (caseSensitive === false) {
          msg = msg.toUpperCase();
        }
        // FIXME: Hacky
        if (msg.search(searchString) === -1) {
          label.setHeight(0);
        } else {
          label.setHeight(15);
        }
      }
    },

    __createInitMsg: function() {
      const who = "System";
      const what = "Logger intialized";
      const logLevel = LOG_LEVEL.debug;
      const whoRich = this.__addWhoColorTag(who);
      const whatRich = this.__addLevelColorTag(what, logLevel);
      const richMsg = whoRich + ": " + whatRich;
      let label = new qx.ui.basic.Label(richMsg).set({
        selectable: true,
        rich: true
      });
      label.who = who;
      label.what = what;
      label.logLevel = logLevel;
      this.__logList.add(label);
    },

    __clearLogger: function() {
      this.__logList.removeAll();
    }
  }
});
