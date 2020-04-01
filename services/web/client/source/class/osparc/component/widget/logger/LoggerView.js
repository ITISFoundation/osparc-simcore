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
 *   let loggerView = new osparc.component.widget.logger.LoggerView(workbench);
 *   this.getRoot().add(loggerView);
 *   loggerView.info(null, "Hello world");
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

qx.Class.define("osparc.component.widget.logger.LoggerView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    const filterToolbar = this.__createFilterToolbar();
    this._add(filterToolbar);

    const table = this.__createTableLayout();
    this._add(table, {
      flex: 1
    });

    this.__messengerColors = new Set();

    this.__createInitMsg();

    this.__textFilterField.addListener("changeValue", this.__applyFilters, this);
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
    },

    currentNodeId: {
      check: "String",
      nullable: true,
      apply: "__currentNodeIdChanged"
    }
  },

  statics: {
    getLevelColorTag: function(logLevel) {
      const colorManager = qx.theme.manager.Color.getInstance();
      for (let i=0; i<LOG_LEVEL.length; i++) {
        const logString = Object.keys(LOG_LEVEL[i])[0];
        const logNumber = LOG_LEVEL[i][logString];
        if (logNumber === logLevel) {
          const logColor = colorManager.resolve("logger-"+logString+"-message");
          return logColor;
        }
      }
      const logColorDef = colorManager.resolve("logger-info-message");
      return logColorDef;
    },

    getNewColor: function() {
      const colorManager = qx.theme.manager.Color.getInstance();
      const luminanceBG = osparc.utils.Utils.getColorLuminance(colorManager.resolve("table-row-background-selected"));
      let luminanceText = null;
      let color = null;
      do {
        color = osparc.utils.Utils.getRandomColor();
        luminanceText = osparc.utils.Utils.getColorLuminance(color);
      } while (Math.abs(luminanceBG-luminanceText) < 0.4);
      return color;
    }
  },

  members: {
    __currentNodeButton: null,
    __textFilterField: null,
    __logModel: null,
    __logView: null,
    __messengerColors: null,

    __createFilterToolbar: function() {
      const toolbar = new qx.ui.toolbar.ToolBar();

      const currentNodeButton = this.__currentNodeButton = new qx.ui.form.ToggleButton(this.tr("This node")).set({
        appearance: "toolbar-button"
      });
      currentNodeButton.addListener("changeValue", e => {
        // this.currectNodeClicked(currentNodeButton.getValue());
        this.currectNodeClicked(e.getData());
      }, this);
      toolbar.add(currentNodeButton);

      toolbar.add(new qx.ui.toolbar.Separator());
      const textFilterField = this.__textFilterField = new qx.ui.form.TextField().set({
        appearance: "toolbar-textfield",
        liveUpdate: true,
        placeholder: this.tr("Filter")
      });
      toolbar.add(textFilterField, {
        flex: 1
      });

      const part = new qx.ui.toolbar.Part();
      const group = new qx.ui.form.RadioGroup();
      let logLevelSet = false;
      for (let i=0; i<LOG_LEVEL.length; i++) {
        const level = Object.keys(LOG_LEVEL[i])[0];
        const logLevel = LOG_LEVEL[i][level];
        if (level === "debug" && !osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
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
      const tableModel = this.__logModel = new osparc.component.widget.logger.RemoteTableModel();

      const custom = {
        tableColumnModel : function(obj) {
          return new qx.ui.table.columnmodel.Resize(obj);
        }
      };

      // table
      const table = this.__logView = new qx.ui.table.Table(tableModel, custom).set({
        selectable: true,
        statusBarVisible: false,
        showCellFocusIndicator: false
      });
      const colModel = table.getTableColumnModel();
      colModel.setDataCellRenderer(0, new qx.ui.table.cellrenderer.Html());
      colModel.setDataCellRenderer(1, new osparc.ui.table.cellrenderer.Html().set({
        defaultCellStyle: "user-select: text"
      }));
      let resizeBehavior = colModel.getBehavior();
      resizeBehavior.setWidth(0, "20%");
      resizeBehavior.setWidth(1, "80%");

      this.__applyFilters();

      return table;
    },

    __currentNodeIdChanged: function() {
      this.__currentNodeButton.setValue(false);
    },

    currectNodeClicked: function(checked) {
      const currentNodeId = this.getCurrentNodeId();
      if (checked) {
        this.__nodeSelected(currentNodeId);
      }
    },

    __nodeSelected: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const node = workbench.getNode(nodeId);
      if (node) {
        this.__textFilterField.setValue(node.getLabel());
      } else {
        // Root selected
        this.__textFilterField.setValue("");
      }
    },

    debug: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], LOG_LEVEL.debug);
    },

    info: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], LOG_LEVEL.info);
    },

    infos: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, LOG_LEVEL.info);
    },

    warn: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], LOG_LEVEL.warning);
    },

    error: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], LOG_LEVEL.error);
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
          this.__logModel.nodeLabelChanged(nodeId, newLabel);
          this.__updateTable();
        }, this);
      } else {
        label = "Workbench";
      }

      const nodeColor = this.__getNodesColor(nodeId);
      const msgColor = osparc.component.widget.logger.LoggerView.getLevelColorTag(logLevel);
      const msgLogs = [];
      for (let i=0; i<msgs.length; i++) {
        const msgLog = {
          nodeId,
          label,
          msg: msgs[i],
          logLevel,
          nodeColor,
          msgColor
        };
        msgLogs.push(msgLog);
      }
      this.__logModel.addRows(msgLogs);

      this.__updateTable();
    },

    __updateTable: function() {
      this.__logModel.reloadData();
      const nFilteredRows = this.__logModel.getFilteredRowCount();
      this.__logView.scrollCellVisible(0, nFilteredRows);
    },

    __getNodesColor: function(nodeId) {
      for (const item of this.__messengerColors) {
        if (item[0] === nodeId) {
          return item[1];
        }
      }
      const color = osparc.component.widget.logger.LoggerView.getNewColor();
      this.__messengerColors.add([nodeId, color]);
      return color;
    },

    __applyFilters: function() {
      if (this.__logModel === null) {
        return;
      }

      this.__logModel.setFilterString(this.__textFilterField.getValue());
      this.__logModel.setFilterLogLevel(this.getLogLevel());
      this.__logModel.reloadData();
    },

    __createInitMsg: function() {
      const nodeId = null;
      const msg = "Logger initialized";
      this.debug(nodeId, msg);
    }
  }
});
