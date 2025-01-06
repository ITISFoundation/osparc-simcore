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
 *   tableModel.setColumns(["Level", "Time", "Origin", "Message"], ["level", "time", "who", "whatRich"]);
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
      "",
      "Time",
      "Origin",
      "Message"
    ], [
      "level",
      "time",
      "who",
      "msgRich"
    ]);

    this.__rawData = [];
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
    getLevelIcon: function(logLevel) {
      const logLevels = osparc.widget.logger.LoggerView.LOG_LEVELS;
      let iconSource = "";
      switch (logLevel) {
        case logLevels.INFO:
          iconSource = "osparc/circle-info-solid.svg";
          break;
        case logLevels.WARNING:
          iconSource = "osparc/circle-exclamation-solid.svg";
          break;
        case logLevels.ERROR:
          iconSource = "osparc/circle-xmark-solid.svg";
          break;
      }
      return iconSource;
    }
  },

  members : {
    __rawData: null,
    __filteredData: null,

    getRows: function() {
      return this.__rawData;
    },

    getFilteredRows: function() {
      return this.__filteredData;
    },

    addRows: function(newRows) {
      newRows.forEach(newRow => {
        newRow["level"] = this.self().getLevelIcon(newRow.logLevel);
        newRow["time"] = osparc.utils.Utils.formatTime(newRow.timeStamp, true);
        newRow["who"] = newRow.label;
        newRow["msgRich"] = newRow.msg.replace(/\n/g, "<br>");
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
      // Fake the server locally
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
