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

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.component.workbench.servicesCatalogue.SearchTypeFilter", {
  extend : qx.core.Object,

  construct: function(controller, props = ["key"]) {
    this.base(arguments);
    // store the controller
    this.__controller = controller;

    // apply the filter funtion on creation time because the 'this' context
    // needs to be bound to the function
    this.filter = qx.lang.Function.bind(data => {
      if (data === undefined || data === null) {
        console.log("Service with no data");
        return false;
      }
      for (let i=0; i<props.length; i++) {
        let getter = "get" + qx.lang.String.firstUp(props[i]);
        const prop = data[getter]();
        if (qxapp.utils.Utils.stringsMatch(prop, this.getSearchString())) {
          return true;
        }
      }
      return false;
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

    // Item's data sorting
    sorter: function(a, b) {
      return a > b;
    },

    __applySearchString: function(value, old) {
      this.__controller.update();
      if (this.__controller.getSelection().length === 0) {
        console.debug("Bug in qooxdoo");
        // TODO: The first time a string is typed, the list doesn't properly change the selected entry
        // Workaround: use "changleValue" on controller instead of "changeSelection" on list
      }
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
