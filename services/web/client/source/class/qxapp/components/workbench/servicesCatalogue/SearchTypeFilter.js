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

    // storage for the timer id
    this.__timerId = null;
  },

  properties: {
    searchString : {
      check : "String",
      apply: "__applySearchString",
      init: ""
    }
  },

  members: {
    __timerId: null,
    __controller: null,

    __applySearchString : function(value, old) {
      // get the timer instance
      var timer = qx.util.TimerManager.getInstance();
      // check for the old listener
      if (this.__timerId !== null) {
        // stop the old one
        timer.stop(this.__timerId);
        this.__timerId = null;
      }
      // start a new listener to update the controller
      this.__timerId = timer.start(function() {
        this.__controller.update();
        this.__timerId = null;
      }, 0, this, null, 200);
    },

    filter: null
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
