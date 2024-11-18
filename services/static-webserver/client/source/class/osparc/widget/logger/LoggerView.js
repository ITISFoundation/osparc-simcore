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
 * Widget that shows a logging view.
 *
 * It consists of:
 * - a toolbar containing:
 *   - clear button
 *   - filter as you type textfield
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
 *   let loggerView = new osparc.widget.logger.LoggerView();
 *   this.getRoot().add(loggerView);
 *   loggerView.info(null, "Hello world");
 * </pre>
 */


qx.Class.define("osparc.widget.logger.LoggerView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    this.__createFilterToolbar();

    const table = this.__createTableLayout();
    this._add(table, {
      flex: 1
    });
  },

  properties: {
    logLevel: {
      apply : "__applyFilters",
      nullable: false,
      check : "Number",
      init: 0
    },

    lockLogs: {
      apply : "__updateTable",
      nullable: false,
      check : "Boolean",
      init: true
    },

    currentNodeId: {
      check: "String",
      nullable: true,
      apply: "__currentNodeIdChanged"
    }
  },

  statics: {
    POS: {
      TIMESTAMP: 0,
      ORIGIN: 1,
      MESSAGE: 2
    },

    LOG_LEVELS: {
      DEBUG: -1,
      INFO: 0,
      WARNING: 1,
      ERROR: 2
    },

    LOG_LEVEL_MAP: {
      10: "DEBUG",
      20: "INFO",
      30: "WARNING",
      40: "ERROR",
      50: "ERROR" // CRITICAL
    },

    printRow: function(rowData) {
      return `${rowData.timeStamp} ${this.self().logLevel2Str(rowData.logLevel)} ${rowData.nodeId} ${rowData.label}: ${rowData.msg}`;
    },

    logLevel2Str: function(logLevel) {
      const pairFound = Object.entries(this.LOG_LEVELS).find(pair => pair[1] === logLevel);
      if (pairFound && pairFound.length) {
        return pairFound[0];
      }
      return undefined;
    }
  },

  members: {
    __textFilterField: null,
    __loggerModel: null,
    __loggerTable: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "toolbar":
          control = new qx.ui.toolbar.ToolBar();
          this._add(control);
          break;
        case "pin-node": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.ToggleButton().set({
            icon: "@FontAwesome5Solid/thumbtack/14",
            toolTipText: this.tr("Show logs only from current node"),
            appearance: "toolbar-button"
          });
          toolbar.add(control);
          break;
        }
        case "filter-text": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.TextField().set({
            appearance: "toolbar-textfield",
            liveUpdate: true,
            placeholder: this.tr("Filter")
          });
          osparc.utils.Utils.setIdToWidget(control, "logsFilterField");
          toolbar.add(control, {
            flex: 1
          });
          break;
        }
        case "log-level": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.SelectBox().set({
            appearance: "toolbar-selectbox",
            maxWidth: 80
          });
          let logLevelSet = false;
          Object.keys(this.self().LOG_LEVELS).forEach(logLevelKey => {
            const logLevel = this.self().LOG_LEVELS[logLevelKey];
            if (logLevelKey === "DEBUG" && !osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
              return;
            }
            const label = qx.lang.String.firstUp(logLevelKey);
            const listItem = new qx.ui.form.ListItem(label);
            control.add(listItem);
            listItem.logLevel = logLevel;
            if (!logLevelSet) {
              this.setLogLevel(logLevel);
              logLevelSet = true;
            }
          });
          toolbar.add(control);
          break;
        }
        case "lock-logs-button": {
          control = new qx.ui.form.ToggleButton().set({
            toolTipText: this.tr("Toggle auto-scroll"),
            appearance: "toolbar-button"
          });
          control.bind("value", this, "lockLogs");
          control.bind("value", control, "icon", {
            converter: val => val ? "@FontAwesome5Solid/lock-open/14" : "@FontAwesome5Solid/lock/14"
          });
          const toolbar = this.getChildControl("toolbar");
          toolbar.add(control);
          break;
        }
        case "copy-to-clipboard": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/copy/14",
            toolTipText: this.tr("Copy logs to clipboard"),
            appearance: "toolbar-button"
          });
          osparc.utils.Utils.setIdToWidget(control, "copyLogsToClipboardButton");
          toolbar.add(control);
          break;
        }
        case "copy-selected-to-clipboard": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/file/14",
            toolTipText: this.tr("Copy Selected log to clipboard"),
            appearance: "toolbar-button"
          });
          toolbar.add(control);
          break;
        }
        case "download-logs-button": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/download/14",
            toolTipText: this.tr("Download logs"),
            appearance: "toolbar-button"
          });
          osparc.utils.Utils.setIdToWidget(control, "downloadLogsButton");
          toolbar.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __createFilterToolbar: function() {
      const toolbar = this.getChildControl("toolbar");

      const pinNode = this.getChildControl("pin-node");
      pinNode.addListener("changeValue", e => this.__pinChanged(e.getData()), this);

      const textFilterField = this.__textFilterField = this.getChildControl("filter-text");
      textFilterField.addListener("changeValue", this.__applyFilters, this);

      const logLevelSelectBox = this.getChildControl("log-level");
      logLevelSelectBox.addListener("changeValue", e => {
        this.setLogLevel(e.getData().logLevel);
      }, this);
      toolbar.add(logLevelSelectBox);

      const lockLogsButton = this.getChildControl("lock-logs-button");
      toolbar.add(lockLogsButton);

      const copyToClipboardButton = this.getChildControl("copy-to-clipboard");
      copyToClipboardButton.addListener("execute", () => this.__copyLogsToClipboard(), this);
      toolbar.add(copyToClipboardButton);

      const copySelectedToClipboardButton = this.getChildControl("copy-selected-to-clipboard");
      copySelectedToClipboardButton.addListener("execute", () => this.__copySelectedLogToClipboard(), this);
      toolbar.add(copySelectedToClipboardButton);

      const downloadButton = this.getChildControl("download-logs-button");
      downloadButton.addListener("execute", () => this.downloadLogs(), this);
      toolbar.add(downloadButton);

      return toolbar;
    },

    __createTableLayout: function() {
      const loggerModel = this.__loggerModel = new osparc.widget.logger.LoggerModel();

      const custom = {
        tableColumnModel : function(obj) {
          return new qx.ui.table.columnmodel.Resize(obj);
        }
      };

      // table
      const table = this.__loggerTable = new qx.ui.table.Table(loggerModel, custom).set({
        selectable: true,
        statusBarVisible: false,
        showCellFocusIndicator: false,
        forceLineHeight: false
      });
      // alwaysUpdateCells
      osparc.utils.Utils.setIdToWidget(table, "logsViewer");
      const colModel = table.getTableColumnModel();
      colModel.setDataCellRenderer(this.self().POS.TIMESTAMP, new osparc.ui.table.cellrenderer.Html().set({
        defaultCellStyle: "user-select: text"
      }));
      colModel.setDataCellRenderer(this.self().POS.ORIGIN, new qx.ui.table.cellrenderer.Html());
      colModel.setDataCellRenderer(this.self().POS.MESSAGE, new osparc.ui.table.cellrenderer.Html().set({
        defaultCellStyle: "user-select: text; text-wrap: wrap"
      }));
      let resizeBehavior = colModel.getBehavior();
      resizeBehavior.setWidth(this.self().POS.TIMESTAMP, 80);
      resizeBehavior.setWidth(this.self().POS.ORIGIN, 100);

      table.setDataRowRenderer(new osparc.ui.table.rowrenderer.ExpandSelection(table));

      this.__applyFilters();

      return table;
    },

    filterByNode: function(nodeId) {
      this.setCurrentNodeId(nodeId);
      this.getChildControl("pin-node").setValue(true);
    },

    __currentNodeIdChanged: function() {
      this.getChildControl("pin-node").setValue(false);
    },

    __pinChanged: function(checked) {
      if (checked) {
        const currentNodeId = this.getCurrentNodeId();
        this.__nodeSelected(currentNodeId);
      }
    },

    __nodeSelected: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const node = workbench.getNode(nodeId);
      this.__textFilterField.setValue(node ? node.getLabel() : "");
    },

    __getLogsString: function() {
      const newLine = "\n";
      let logs = "";
      this.__loggerModel.getFilteredRows().forEach(rowData => {
        logs += this.self().printRow(rowData) + newLine;
      });
      return logs;
    },

    __copyLogsToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.__getLogsString());
    },

    __copySelectedLogToClipboard: function() {
      const sel = this.__loggerTable.getSelectionModel().getAnchorSelectionIndex();
      if (sel > -1) {
        const rowData = this.__loggerModel.getRowData(sel);
        osparc.utils.Utils.copyTextToClipboard(this.self().printRow(rowData));
      }
    },

    downloadLogs: function() {
      const logs = this.__getLogsString();
      const blob = new Blob([logs], {type: "text/plain"});
      osparc.utils.Utils.downloadBlobContent(blob, "logs.log");
    },

    debug: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.DEBUG);
    },

    info: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.INFO);
    },

    warn: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.WARNING);
    },

    error: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.ERROR);
    },

    debugs: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, this.self().LOG_LEVELS.DEBUG);
    },

    infos: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, this.self().LOG_LEVELS.INFO);
    },

    warns: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, this.self().LOG_LEVELS.WARNING);
    },

    errors: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, this.self().LOG_LEVELS.ERROR);
    },

    __addLogs: function(nodeId, msgs = [""], logLevel = 0) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      if (study === null) {
        return;
      }

      const workbench = study.getWorkbench();
      const node = workbench.getNode(nodeId);
      let label = null;
      if (node) {
        label = node.getLabel();
        node.addListener("changeLabel", e => {
          const newLabel = e.getData();
          this.__loggerModel.nodeLabelChanged(nodeId, newLabel);
          this.__updateTable();
        }, this);
      } else {
        label = "Workbench";
      }

      const msgLogs = [];
      msgs.forEach(msg => {
        const msgLog = {
          timeStamp: new Date(),
          nodeId,
          label,
          msg,
          tooltip: msg,
          logLevel
        };
        msgLogs.push(msgLog);
      });
      this.__loggerModel.addRows(msgLogs);

      this.__updateTable();
    },

    __updateTable: function() {
      if (this.__loggerModel) {
        this.__loggerModel.reloadData();
        // isWidgetOnScreen will avoid rendering every single line when the user click on the Logger button the first time
        if (!this.isLockLogs() && osparc.utils.Utils.isWidgetOnScreen(this.__loggerTable)) {
          const nFilteredRows = this.__loggerModel.getFilteredRowCount();
          this.__loggerTable.scrollCellVisible(0, nFilteredRows);
        }
      }
    },

    __applyFilters: function() {
      if (this.__loggerModel === null) {
        return;
      }

      this.__loggerModel.setFilterString(this.__textFilterField.getValue());
      this.__loggerModel.setFilterLogLevel(this.getLogLevel());
      this.__loggerModel.reloadData();
    }
  }
});
