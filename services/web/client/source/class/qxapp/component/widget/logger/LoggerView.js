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

const LOG_LEVEL = {
  debug: -1,
  info: 0,
  warning: 1,
  error: 2
};
Object.freeze(LOG_LEVEL);

qx.Class.define("qxapp.component.widget.logger.LoggerView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(10));

    let filterLayout = this.__createFilterLayout();
    this._add(filterLayout);

    let table = this.__createTableLayout();
    this._add(table, {
      flex: 1
    });

    this.__logs = [];
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
    __logs: null,
    __logModel: null,
    __logView: null,
    __messengerColors: null,

    __createFilterLayout: function() {
      let filterLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      let clearButton = new qx.ui.form.Button("Clear");
      clearButton.addListener("execute", e => {
        this.clearLogger();
      }, this);
      filterLayout.add(clearButton);

      let searchLabel = new qx.ui.basic.Label(this.tr("Filter"));
      filterLayout.add(searchLabel);
      this.__textfield = new qx.ui.form.TextField();
      this.__textfield.setLiveUpdate(true);
      filterLayout.add(this.__textfield, {
        flex: 1
      });

      let logLevelButtons = new qx.ui.toolbar.Part();
      let logLevelBtns = [];
      for (var key in LOG_LEVEL) {
        let text = String(key)[0].toUpperCase() + String(key).slice(1);
        let filterButton = new qx.ui.form.ToggleButton(text);
        filterButton.logLevel = LOG_LEVEL[key];
        logLevelButtons.add(filterButton);
        logLevelBtns.push(filterButton);
      }
      filterLayout.add(logLevelButtons);

      let group = new qx.ui.form.RadioGroup();
      let defSelected = [];
      for (let i=0; i<logLevelBtns.length; i++) {
        let logLevelBtn = logLevelBtns[i];
        group.add(logLevelBtn);
        if (this.getLogLevel() === logLevelBtn.logLevel) {
          defSelected.push(logLevelBtn);
        }
        logLevelBtn.addListener("changeValue", e => {
          if (e.getData() === true) {
            this.setLogLevel(logLevelBtn.logLevel);
          }
        }, this);
      }
      group.setSelection(defSelected);
      group.setAllowEmptySelection(false);

      return filterLayout;
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

      return table;
    },

    debug: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.debug);
    },

    info: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.info);
    },

    warn: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.warning);
    },

    error: function(who = "System", what = "") {
      this.__addLog(who, what, LOG_LEVEL.error);
    },

    __addLog: function(who = "System", what = "", logLevel = 0) {
      this.__logs.push({
        who: who,
        what: what,
        logLevel: logLevel
      });

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
      const keyStr = String(qxapp.utils.Utils.getKeyByValue(LOG_LEVEL, logLevel));
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
