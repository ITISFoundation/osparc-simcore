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
 *   let tableModel = this.__logModel = new osparc.component.widget.logger.LoggerTable();
 *   tableModel.setColumns(["Origin", "Message"], ["whoRich", "whatRich"]);
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

qx.Class.define("osparc.component.widget.logger.LoggerTable", {
  extend : qx.ui.table.model.Remote,

  construct : function() {
    this.base(arguments);

    this.setColumns([
      "Origin",
      "Message"
    ], [
      "whoRich",
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
      const logLevels = osparc.component.widget.logger.LoggerView.LOG_LEVELS;
      Object.keys(logLevels).forEach(logLevelKey => {
        const logString = logLevelKey;
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
        newRow["whoRich"] = this.self().addColorTag(newRow.label, newRow.nodeColor);
        newRow["msgRich"] = this.self().addColorTag(newRow.msg, newRow.msgColor);
        this.__rawData.push(newRow);
      });
    },

    nodeLabelChanged: function(nodeId, newLabel) {
      this.__rawData.forEach(row => {
        if (row.nodeId === nodeId) {
          row.label = newLabel;
          row["whoRich"] = this.self().addColorTag(row.label, row.nodeColor);
        }
      });
    },

    __themeChanged: function() {
      this.__rawData.forEach(row => {
        row["msgColor"] = osparc.component.widget.logger.LoggerTable.getLevelColor(row.logLevel);
        row["msgRich"] = this.self().addColorTag(row.msg, row.msgColor);
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

    // overloaded - called whenever the table requests the row count
    _loadRowCount : function() {
      this.__filteredData = [];
      for (let i=0; i<this.__rawData.length; i++) {
        const rowData = this.__rawData[i];
        if (this.__checkFilters(rowData)) {
          this.__filteredData.push(rowData);
        }
      }
      this.__setRowCount(this.__filteredData.length);
    },

    _loadRowData : function(firstRow, lastRow) {
      this.__rowDataLoadded(firstRow, lastRow);
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

    // Fake the server localy
    __setRowCount : function(number) {
      var self = this;
      self._onRowCountLoaded(number);
    },

    __rowDataLoadded : function(firstRow, lastRow) {
      var self = this;
      var data = [];
      for (var i=firstRow; i<=lastRow; i++) {
        data.push(this.__filteredData[i]);
      }
      self._onRowDataLoaded(data);
    }
  }
});
