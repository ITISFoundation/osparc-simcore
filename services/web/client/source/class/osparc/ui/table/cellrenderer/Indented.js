/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.table.cellrenderer.Indented", {
  extend: qx.ui.table.cellrenderer.Default,

  construct: function(indentation) {
    this.base(arguments);
    if (indentation) {
      this.setIndentation(indentation);
    } else {
      this.__updateIndentation();
    }
  },

  statics: {
    TAB_SIZE: 4
  },

  properties: {
    indentation: {
      check: "Integer",
      nullable: false,
      init: 0,
      apply: "_applyIndentation"
    }
  },

  members: {
    __indentString: null,
    // overridden
    _getContentHtml: function(cellInfo) {
      const pre = this.base(arguments, cellInfo);
      return this.__indentString + pre;
    },

    _applyIndentation: function() {
      this.__updateIndentation();
    },

    __updateIndentation: function() {
      const tab = Array(this.self().TAB_SIZE + 1).join("&nbsp;");
      this.__indentString = Array(this.getIndentation() + 1).join(tab);
    }
  }
});
