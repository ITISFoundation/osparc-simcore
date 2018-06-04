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

qx.Class.define("qxapp.components.workbench.logger.RemoteTableModel", {

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
      nullable: false,
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

    addRows: function(newRows) {
      for (let i=0; i<newRows.length; i++) {
        this.__rawData.push(newRows[i]);
      }
    },


    // overloaded - called whenever the table requests the row count
    _loadRowCount : function() {
      this.__setRowCount(this.__rawData.length);
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

      return (showStrWho && showStrWhat && showLog);
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
        if (i < this.__rawData.length) {
          const rowData = this.__rawData[i];
          if (this.__checkFilters(rowData[2])) {
            data.push(rowData);
          }
        }
      }
      self._onRowDataLoaded(data);
    }
  }
});
