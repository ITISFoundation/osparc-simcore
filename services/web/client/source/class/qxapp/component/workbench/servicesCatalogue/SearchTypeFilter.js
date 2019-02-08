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

    this.clearFilters();

    // apply the filter funtion on creation time because the 'this' context
    // needs to be bound to the function
    this.filter = qx.lang.Function.bind(data => {
      if (data === undefined || data === null) {
        console.log("Service with no data");
        return false;
      }
      for (let i=0; i<props.length; i++) {
        const prop = this.__getPropValue(data, props[i]);
        if (qxapp.utils.Utils.stringsMatch(prop, this.getSearchString())) {
          if (this.__checkExtraFilters(data)) {
            return true;
          }
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
    __extraFilters: null,
    filter: null,

    // Item's data sorting
    sorter: function(a, b) {
      return a > b;
    },

    __getPropValue: function(data, propName) {
      let getter = "get" + qx.lang.String.firstUp(propName);
      return data[getter]();
    },

    __applySearchString: function(value, old) {
      this.__controller.update();
      if (this.__controller.getSelection().length === 0) {
        console.debug("Bug in qooxdoo");
        // TODO: The first time a string is typed, the list doesn't properly change the selected entry
        // Workaround: use "changleValue" on controller instead of "changeSelection" on list
      }
    },

    __checkExtraFilters: function(data) {
      if (Object.keys(this.__extraFilters).length > 0) {
        for (const filterKey in this.__extraFilters) {
          const prop = this.__getPropValue(data, filterKey);
          if (prop.toLowerCase() !== this.__extraFilters[filterKey]) {
            return false;
          }
        }
      }
      return true;
    },

    clearFilters: function() {
      this.__extraFilters = {};
    },

    addFilter: function(propName, propValue) {
      this.__extraFilters[propName.toLowerCase()] = propValue.toLowerCase();
    },

    removeFilter: function(propName) {
      delete this.__extraFilters[propName.toLowerCase()];
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
