/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)
     * Odei Maiz (odemaiz)

************************************************************************ */

/**
 * Widget that contains the study filters.
 */
qx.Class.define("qxapp.desktop.StudyFilters", {
  extend: qx.ui.core.Widget,

  construct: function(groupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    const textFilter = this.__textFilter = new qxapp.component.filter.TextFilter("text", groupId);
    qxapp.utils.Utils.setIdToWidget(textFilter, "studyFiltersTextFld");
    this._add(textFilter);
  },

  members: {
    __textFilter: null,

    /**
     * Resets the text
     */
    reset: function() {
      this.__textFilter.reset();
    },

    getTextFilter: function() {
      return this.__textFilter;
    }
  }
});
