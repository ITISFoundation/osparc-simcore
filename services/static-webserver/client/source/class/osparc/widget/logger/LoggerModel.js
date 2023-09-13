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

/* eslint no-underscore-dangle: "off" */

/**
 * Remote table model for showing log messages
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let tableModel = this.__logModel = new osparc.widget.logger.LoggerTable();
 *   tableModel.setColumns(["Timestamp", "Origin", "Message"], ["time", "who", "whatRich"]);
 *   let custom = {
 *     tableColumnModel : function(obj) {
 *       return new qx.ui.table.columnmodel.Resize(obj);
 *     }
 *   };
 *   let table = new qx.ui.table.Table(tableModel, custom);
 *   this.getRoot().add(table);
 * </pre>
 */

/**
 *
 * @asset(demobrowser/backend/remote_table.php)
 */

qx.Class.define("osparc.widget.logger.LoggerModel", {
  extend : qx.ui.table.model.Remote,

  construct : function() {
    this.base(arguments);

    this.setColumns([
      "Time",
      "Origin",
      "Message"
    ], [
      "time",
      "who",
      "msgRich"
    ]);

    this.__rawData = [];

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => this.__themeChanged());
  },

  properties: {
    filterLogLevel: {
      nullable: false,
      check : "Number",
      init: -1
    },

    filterString: {
      nullable: true,
      check : "String",
      init: ""
    }
  },

  statics: {
    addColorTag: function(msg, color) {
      return ("<font color=" + color +">" + msg + "</font>");
    },

    getLevelColor: function(logLevel) {
      const colorManager = qx.theme.manager.Color.getInstance();
      let logColor = null;
      const logLevels = osparc.widget.logger.LoggerView.LOG_LEVELS;
      Object.keys(logLevels).forEach(logLevelKey => {
        const logString = logLevelKey.toLowerCase();
        const logNumber = logLevels[logLevelKey];
        if (logNumber === logLevel) {
          logColor = colorManager.resolve("logger-"+logString+"-message");
        }
      });
      return logColor ? logColor : colorManager.resolve("logger-info-message");
    }
  },

  members : {
    __rawData: null,
    __filteredData: null,

    getRows: function() {
      return this.__rawData;
    },

    addRows: function(newRows) {
      newRows.forEach(newRow => {
        const levelColor = this.self().getLevelColor(newRow.logLevel);
        newRow["time"] = osparc.utils.Utils.formatTime(newRow.timeStamp, true);
        newRow["who"] = newRow.label;
        newRow["msgRich"] = this.self().addColorTag(newRow.msg, levelColor);
        this.__rawData.push(newRow);
      });
    },

    nodeLabelChanged: function(nodeId, newLabel) {
      this.__rawData.forEach(row => {
        if (row.nodeId === nodeId) {
          row.label = newLabel;
          row["who"] = row.label;
        }
      });
    },

    __themeChanged: function() {
      this.__rawData.forEach(row => {
        const levelColor = this.self().getLevelColor(row.logLevel);
        row["time"] = osparc.utils.Utils.formatTime(row.timeStamp, true);
        row["who"] = row.label;
        row["msgRich"] = this.self().addColorTag(row.msg, levelColor);
      });
    },

    clearTable: function() {
      const rawLength = this.__rawData.length;
      this.__rawData = [];
      for (let i=rawLength-1; i>=0; i--) {
        this.removeRow(i);
      }
      this.reloadData();
    },

    getRawRowCount: function() {
      return this.__rawData.length;
    },

    getFilteredRowCount: function() {
      return this.__filteredData.length;
    },

    __filterByString: function(msg) {
      let searchString = this.getFilterString();
      if (searchString === null || searchString === "") {
        return true;
      }
      searchString = searchString.toUpperCase();
      if (msg) {
        msg = msg.toUpperCase();
        return msg.includes(searchString);
      }
      return false;
    },

    __filterByLogLevel: function(logLevel) {
      const show = logLevel >= this.getFilterLogLevel();
      return show;
    },

    __checkFilters: function(rowData) {
      const showStrWho = this.__filterByString(rowData.label);
      const showStrWhat = this.__filterByString(rowData.msg);
      const showLog = this.__filterByLogLevel(rowData.logLevel);

      return ((showStrWho || showStrWhat) && showLog);
    },

    // overloaded - called whenever the table requests the row count
    _loadRowCount: function() {
      this.__filteredData = [];
      for (let i=0; i<this.__rawData.length; i++) {
        const rowData = this.__rawData[i];
        if (this.__checkFilters(rowData)) {
          this.__filteredData.push(rowData);
        }
      }
      // Fake the server localy
      const self = this;
      self._onRowCountLoaded(this.__filteredData.length);
    },

    // overridden
    _loadRowData: function(firstRow, lastRow) {
      const data = [];
      for (let i=firstRow; i<=lastRow; i++) {
        data.push(this.__filteredData[i]);
      }
      const self = this;
      self._onRowDataLoaded(data);
    }
  }
});
