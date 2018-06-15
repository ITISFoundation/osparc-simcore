qx.Class.define("qxapp.components.workbench.servicesCatalogue.SearchTypeFilter", {
  extend : qx.core.Object,

  construct: function(controller) {
    this.base(arguments);
    // store the controller
    this.__controller = controller;

    // apply the filter funtion on creation time because the 'this' context
    // needs to be bound to the function
    this.filter = qx.lang.Function.bind(function(data) {
      const caseSensitive = false;
      let searchString = this.getSearchString();
      if (caseSensitive === false) {
        data = data.toUpperCase();
        searchString = searchString.toUpperCase();
      }
      return data.search(searchString) != -1;
    }, this);
  },

  properties: {
    searchString : {
      check : "String",
      apply: "__applySearchString",
      init: ""
    }
  },

  members: {
    __controller: null,
    filter: null,

    __applySearchString : function(value, old) {
      this.__controller.update();
    }
  },

  /*
   *****************************************************************************
      DESTRUCT
   *****************************************************************************
   */

  destruct : function() {
    this.__controller = null;
  }
});
