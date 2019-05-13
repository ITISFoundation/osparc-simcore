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
 * Widget that shows a logging view.
 *
 * It consists of:
 * - a toolbar containing:
 *   - clear button
 *   - filter as you type textfiled
 *   - some log type filtering buttons
 * - log messages table
 *
 * Log messages have two inputs: "Origin" and "Message".
 *
 *   Depending on the log level, "Origin"'s color will change, also "Message"s coming from the same
 * origin will be rendered with the same color.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let loggerView = new qxapp.component.widget.logger.LoggerView();
 *   this.getRoot().add(loggerView);
 *   loggerView.info("Workbench", "Hello world");
 * </pre>
 */

const LOG_LEVEL = [
  {
    debug: -1
  }, {
    info: 0
  }, {
    warning: 1
  }, {
    error: 2
  }
];
Object.freeze(LOG_LEVEL);

qx.Class.define("qxapp.component.widget.logger.LoggerView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    let filterToolbar = this.__createFilterToolbar();
    this._add(filterToolbar);

    let table = this.__createTableLayout();
    this._add(table, {
      flex: 1
    });

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
      init: LOG_LEVEL[0].debug
    },

    caseSensitive: {
      nullable: false,
      check : "Boolean",
      init: false
    }
  },

  members: {
    __textfield: null,
    __logModel: null,
    __logView: null,
    __messengerColors: null,

    __createFilterToolbar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();

      const clearButton = new qx.ui.toolbar.Button(this.tr("Clear"), "@FontAwesome5Solid/ban/16");
      clearButton.addListener("execute", e => {
        this.clearLogger();
      }, this);
      toolbar.add(clearButton);

      toolbar.add(new qx.ui.toolbar.Separator());
      this.__textfield = new qx.ui.form.TextField().set({
        appearance: "toolbar-textfield",
        liveUpdate: true,
        placeholder: this.tr("Filter")
      });
      toolbar.add(this.__textfield, {
        flex: 1
      });

      const part = new qx.ui.toolbar.Part();
      const group = new qx.ui.form.RadioGroup();
      let logLevelSet = false;
      for (let i=0; i<LOG_LEVEL.length; i++) {
        const level = Object.keys(LOG_LEVEL[i])[0];
        const logLevel = LOG_LEVEL[i][level];
        if (level === "debug" && !qxapp.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
          continue;
        }
        const label = level.charAt(0).toUpperCase() + level.slice(1);
        const button = new qx.ui.form.ToggleButton(label).set({
          appearance: "toolbar-button"
        });
        button.logLevel = logLevel;
        group.add(button);
        part.add(button);
        if (!logLevelSet) {
          this.setLogLevel(logLevel);
          logLevelSet = true;
        }
      }
      group.addListener("changeValue", e => {
        this.setLogLevel(e.getData().logLevel);
      }, this);
      toolbar.add(part);

      return toolbar;
    },

    __createTableLayout: function() {
      // let tableModel = this.__logModel = new qx.ui.table.model.Filtered();
      let tableModel = this.__logModel = new qxapp.component.widget.logger.RemoteTableModel();
      tableModel.setColumns(["Origin", "Message"], ["whoRich", "whatRich"]);

      let custom = {
        tableColumnModel : function(obj) {
          return new qx.ui.table.columnmodel.Resize(obj);
        }
      };

      // table
      let table = this.__logView = new qx.ui.table.Table(tableModel, custom).set({
        selectable: true,
        statusBarVisible: false
      });
      var colModel = table.getTableColumnModel();
      colModel.setDataCellRenderer(0, new qx.ui.table.cellrenderer.Html());
      colModel.setDataCellRenderer(1, new qx.ui.table.cellrenderer.Html());
      let resizeBehavior = colModel.getBehavior();
      resizeBehavior.setWidth(0, "15%");
      resizeBehavior.setWidth(1, "85%");

      this.__applyFilters();

      return table;
    },

    debug: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL[0].debug);
    },

    info: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL[1].info);
    },

    infos: function(who = "System", whats = [""]) {
      this.__addLogs(who, whats, LOG_LEVEL[1].info);
    },

    warn: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL[2].warning);
    },

    error: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL[3].error);
    },

    __addLog: function(who = "System", what = "", logLevel = 0) {
      const whoRich = this.__addWhoColorTag(who);
      const whatRich = this.__addLevelColorTag(what, logLevel);
      let msgLog = {
        whoRich: whoRich,
        whatRich: whatRich,
        msg: {
          who: who,
          what: what,
          logLevel: logLevel
        }
      };
      this.__logModel.addRows([msgLog]);

      this.__updateTable();
    },

    __addLogs: function(who = "System", whats = [""], logLevel = 0) {
      const whoRich = this.__addWhoColorTag(who);

      let msgLogs = [];
      for (let i=0; i<whats.length; i++) {
        const whatRich = this.__addLevelColorTag(whats[i], logLevel);
        const msgLog = {
          whoRich: whoRich,
          whatRich: whatRich,
          msg: {
            who: who,
            what: whats[i],
            logLevel: logLevel
          }
        };
        msgLogs.push(msgLog);
      }
      this.__logModel.addRows(msgLogs);

      this.__updateTable();
    },

    __updateTable: function(who) {
      this.__logModel.reloadData();
      const nFilteredRows = this.__logModel.getFilteredRowCount();
      this.__logView.scrollCellVisible(0, nFilteredRows);
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
        const luminanceBG = qxapp.utils.Utils.getColorLuminance(qxapp.theme.Color.colors["table-row-background-selected"]);
        let luminanceText = null;
        do {
          whoColor = qxapp.utils.Utils.getRandomColor();
          luminanceText = qxapp.utils.Utils.getColorLuminance(whoColor);
        } while (Math.abs(luminanceBG-luminanceText) < 0.4);

        this.__messengerColors.add([who, whoColor]);
      }

      return ("<font color=" + whoColor +">" + who + "</font>");
    },

    __addLevelColorTag: function(what, logLevel) {
      let keyStr = "info";
      for (let i=0; i<LOG_LEVEL.length; i++) {
        const level = Object.keys(LOG_LEVEL[i])[0];
        if (LOG_LEVEL[i][level] === logLevel) {
          keyStr = level;
          break;
        }
      }
      const logColor = qxapp.theme.Color.colors["logger-"+keyStr+"-message"];
      return ("<font color=" + logColor +">" + what + "</font>");
    },

    __applyFilters: function() {
      if (this.__logModel === null) {
        return;
      }

      this.__logModel.setFilterString(this.__textfield.getValue());
      this.__logModel.setFilterLogLevel(this.getLogLevel());
      this.__logModel.reloadData();
    },

    __createInitMsg: function() {
      const who = "System";
      const what = "Logger initialized";
      this.debug(who, what);
    },

    clearLogger: function() {
      this.__logModel.clearTable();
    }
  }
});
