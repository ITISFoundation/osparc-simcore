/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Widget that contains the workbench filters
 */

qx.Class.define("qxapp.desktop.ServiceFilters", {
  extend: qx.ui.core.Widget,

  construct: function(groupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    const textFilter = this.__textFilter = new qxapp.component.filter.TextFilter("text", groupId);
    const tagsFilter = this.__tagsFilter = new qxapp.component.filter.TagsFilter("tags", groupId);
    this._add(textFilter);
    this._add(tagsFilter);
  },

  members: {
    __textFilter: null,

    getTextFilter: function() {
      return this.__textFilter;
    }
  }
});
