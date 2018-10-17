/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2004-2010 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     MIT: https://opensource.org/licenses/MIT
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Tobias Oetiker
     * martinwittemann (martinwittemann)

************************************************************************ */
/* ************************************************************************


************************************************************************ */
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
