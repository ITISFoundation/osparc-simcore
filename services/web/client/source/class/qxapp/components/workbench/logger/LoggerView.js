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

    let filterLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

    let clearButton = new qx.ui.form.Button("Clear");
    clearButton.addListener("execute", function(e) {
      this.clearLogger();
    }, this);
    filterLayout.add(clearButton);

    let searchLabel = new qx.ui.basic.Label("Filter");
    filterLayout.add(searchLabel);
    this.__textfield = new qx.ui.form.TextField();
    this.__textfield.setLiveUpdate(true);
    filterLayout.add(this.__textfield, {
      flex: 1
    });

    var logLevelButtons = new qx.ui.toolbar.Part();

    let showDebugButton = new qx.ui.form.ToggleButton("Debug");
    showDebugButton.logLevel = LOG_LEVEL.debug;
    logLevelButtons.add(showDebugButton);

    let showInfoButton = new qx.ui.form.ToggleButton("Info");
    showInfoButton.logLevel = LOG_LEVEL.info;
    logLevelButtons.add(showInfoButton);

    let showWarnButton = new qx.ui.form.ToggleButton("Warning");
    showWarnButton.logLevel = LOG_LEVEL.warning;
    logLevelButtons.add(showWarnButton);

    let showErrorButton = new qx.ui.form.ToggleButton("Error");
    showErrorButton.logLevel = LOG_LEVEL.error;
    logLevelButtons.add(showErrorButton);

    filterLayout.add(logLevelButtons);

    let logLevelBtns = [showDebugButton, showInfoButton, showWarnButton, showErrorButton];

    let group = new qx.ui.form.RadioGroup();
    let defSelected = [];
    for (let i=0; i<logLevelBtns.length; i++) {
      let logLevelBtn = logLevelBtns[i];
      group.add(logLevelBtn);
      if (this.getLogLevel() === logLevelBtn.logLevel) {
        defSelected.push(logLevelBtn);
      }
      logLevelBtn.addListener("changeValue", function(e) {
        if (e.getData() === true) {
          this.setLogLevel(logLevelBtn.logLevel);
        }
      }, this);
    }
    group.setSelection(defSelected);
    group.setAllowEmptySelection(false);

    this.add(filterLayout);

    let scroller = new qx.ui.container.Scroll();
    this.add(scroller, {
      flex: 1
    });

    this.__logList = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    scroller.add(this.__logList);

    this.__messengerColors = new Set();

    this.__createInitMsg();

    this.__textfield.addListener("changeValue", this.__applyFilters, this);
  },

  events: {},

  properties: {
    logLevel: {
      apply : "__applyFilters",
      nullable: false,
      check : "Number",
      init: LOG_LEVEL.debug
    },
    caseSensitive: {
      nullable: false,
      check : "Boolean",
      init: false
    }
  },

  members: {
    __textfield: null,
    __logList: null,
    __messengerColors: null,

    addLogDebug: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.debug);
    },

    addLogInfo: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.info);
    },

    addLogWarning: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.warning);
    },

    addLogError: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.error);
    },

    __addLog: function(who = "System", what = "", logLevel = 0) {
      const whoRich = this.__addWhoColorTag(who);
      const whatRich = this.__addLevelColorTag(what, logLevel);
      const richMsg = whoRich + whatRich;
      let label = new qx.ui.basic.Label(richMsg).set({
        selectable: true,
        rich: true
      });
      label.who = who;
      label.what = what;
      label.logLevel = logLevel;
      this.__logList.add(label);

      let show = label.logLevel >= this.getLogLevel();
      this.__showMessage(label, show);
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

      return ("<font color=" + whoColor +">" + who + ": </font>");
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

    __showMessage: function(label, show) {
      // FIXME: Hacky
      if (show) {
        label.setHeight(15);
      } else {
        label.setHeight(0);
      }
    },

    __filterByString: function(label) {
      let searchString = this.__textfield.getValue();
      if (searchString === null) {
        return true;
      }
      if (searchString && !this.isCaseSensitive()) {
        searchString = searchString.toUpperCase();
      }
      let msg = label.who + ": " + label.what;
      if (!this.isCaseSensitive()) {
        msg = msg.toUpperCase();
      }
      const show = msg.includes(searchString);
      return show;
    },

    __filterByLogLevel: function(label) {
      const show = label.logLevel >= this.getLogLevel();
      return show;
    },

    __applyFilters: function() {
      if (this.__logList === null) {
        return;
      }

      for (let i=0; i<this.__logList.getChildren().length; i++) {
        let label = this.__logList.getChildren()[i];
        const showStr = this.__filterByString(label);
        const showLog = this.__filterByLogLevel(label);
        this.__showMessage(label, showStr && showLog);
      }
    },

    __createInitMsg: function() {
      const who = "System";
      const what = "Logger intialized";
      this.addLogDebug(who, what);
    },

    clearLogger: function() {
      this.__logList.removeAll();
    }
  }
});
