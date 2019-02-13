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
 * Remote table model for showing log messages
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let tableModel = this.__logModel = new qxapp.component.widget.logger.RemoteTableModel();
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

/* eslint no-underscore-dangle: "off" */

qx.Class.define("qxapp.component.widget.logger.RemoteTableModel", {

  extend : qx.ui.table.model.Remote,

  construct : function() {
    this.base(arguments);
    // this.setColumns(["Id", "Text"], ["id", "text"]);
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
    },
    caseSensitive: {
      nullable: false,
      check : "Boolean",
      init: false
    }
  },

  members : {
    __rawData: null,
    __filteredData: null,

    addRows: function(newRows) {
      for (let i=0; i<newRows.length; i++) {
        this.__rawData.push(newRows[i]);
      }
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
        if (this.__checkFilters(rowData.msg)) {
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
      if (searchString === null) {
        return true;
      }
      if (searchString && !this.isCaseSensitive()) {
        searchString = searchString.toUpperCase();
      }
      if (!this.isCaseSensitive()) {
        msg = msg.toUpperCase();
      }
      const show = msg.includes(searchString);
      return show;
    },

    __filterByLogLevel: function(logLevel) {
      const show = logLevel >= this.getFilterLogLevel();
      return show;
    },

    __checkFilters: function(rowData) {
      const showStrWho = this.__filterByString(rowData.who);
      const showStrWhat = this.__filterByString(rowData.what);
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
