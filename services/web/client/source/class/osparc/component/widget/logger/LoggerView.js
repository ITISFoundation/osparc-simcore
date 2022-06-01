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
 *   let loggerView = new osparc.component.widget.logger.LoggerView();
 *   this.getRoot().add(loggerView);
 *   loggerView.info(null, "Hello world");
 * </pre>
 */


qx.Class.define("osparc.component.widget.logger.LoggerView", {
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

    currentNodeId: {
      check: "String",
      nullable: true,
      apply: "__currentNodeIdChanged"
    }
  },

  statics: {
    LOG_LEVELS: {
      debug: -1,
      info: 0,
      warning: 1,
      error: 2
    }
  },

  members: {
    __textFilterField: null,
    __loggerModel: null,
    __logView: null,

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
            if (logLevelKey === "debug" && !osparc.data.Permissions.getInstance().canDo("study.logger.debug.read")) {
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
      }
      return control || this.base(arguments, id);
    },

    __createFilterToolbar: function() {
      const toolbar = this.getChildControl("toolbar");

      const pinNode = this.getChildControl("pin-node");
      pinNode.addListener("changeValue", e => {
        this.__currentNodeClicked(e.getData());
      }, this);

      const textFilterField = this.__textFilterField = this.getChildControl("filter-text");
      textFilterField.addListener("changeValue", this.__applyFilters, this);

      const logLevelSelectBox = this.getChildControl("log-level");
      logLevelSelectBox.addListener("changeValue", e => {
        this.setLogLevel(e.getData().logLevel);
      }, this);
      toolbar.add(logLevelSelectBox);

      const copyToClipboardButton = this.getChildControl("copy-to-clipboard");
      copyToClipboardButton.addListener("execute", () => this.__copyLogsToClipboard(), this);
      toolbar.add(copyToClipboardButton);

      return toolbar;
    },

    __createTableLayout: function() {
      const loggerModel = this.__loggerModel = new osparc.component.widget.logger.LoggerTable();

      const custom = {
        tableColumnModel : function(obj) {
          return new qx.ui.table.columnmodel.Resize(obj);
        }
      };

      // table
      const table = this.__logView = new qx.ui.table.Table(loggerModel, custom).set({
        selectable: true,
        statusBarVisible: false,
        showCellFocusIndicator: false
      });
      osparc.utils.Utils.setIdToWidget(table, "logsViewer");
      const colModel = table.getTableColumnModel();
      colModel.setDataCellRenderer(0, new qx.ui.table.cellrenderer.Html());
      colModel.setDataCellRenderer(1, new osparc.ui.table.cellrenderer.Html().set({
        defaultCellStyle: "user-select: text"
      }));
      colModel.setDataCellRenderer(2, new osparc.ui.table.cellrenderer.Html().set({
        defaultCellStyle: "user-select: text"
      }));
      let resizeBehavior = colModel.getBehavior();
      resizeBehavior.setWidth(0, "15%");
      resizeBehavior.setWidth(1, "10%");
      resizeBehavior.setWidth(2, "75%");

      this.__applyFilters();

      return table;
    },

    __currentNodeIdChanged: function() {
      this.getChildControl("pin-node").setValue(false);
    },

    __currentNodeClicked: function(checked) {
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

    __copyLogsToClipboard: function() {
      let logs = "";
      this.__loggerModel.getRows().forEach(row => {
        logs += `(${row.nodeId}) ${row.label}: ${row.msg} \n`;
      });
      osparc.utils.Utils.copyTextToClipboard(logs);
    },

    debug: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.debug);
    },

    info: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.info);
    },

    infos: function(nodeId, msgs = [""]) {
      this.__addLogs(nodeId, msgs, this.self().LOG_LEVELS.info);
    },

    warn: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.warning);
    },

    error: function(nodeId, msg = "") {
      this.__addLogs(nodeId, [msg], this.self().LOG_LEVELS.error);
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
          nodeId,
          label,
          timeStamp: new Date(),
          msg,
          logLevel
        };
        msgLogs.push(msgLog);
      });
      this.__loggerModel.addRows(msgLogs);

      this.__updateTable();
    },

    __updateTable: function() {
      this.__loggerModel.reloadData();
      const nFilteredRows = this.__loggerModel.getFilteredRowCount();
      this.__logView.scrollCellVisible(0, nFilteredRows);
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
