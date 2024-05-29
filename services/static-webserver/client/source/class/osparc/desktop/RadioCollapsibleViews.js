/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (ignapas)

************************************************************************ */

qx.Class.define("osparc.desktop.RadioCollapsibleViews", {
  extend: qx.core.Object,

  /**
   * @param {Array} collapsibleViews array of osparc.widget.CollapsibleView
   */
  construct: function(collapsibleViews = []) {
    this.base(arguments);

    this.__collapsibleViews = collapsibleViews;
  },

  members: {
    __collapsibleViews: null,

    /**
     * @param {osparc.widget.CollapsibleView} collapsibleView
     */
    addCollapsibleView: function(collapsibleView) {
      this.__collapsibleViews.push(collapsibleView);
    },

    openCollapsibleView: function(idx = 0) {
      this.__collapsibleViews.forEach(cv => cv.setCollapsed(true));
      if (idx < this.__collapsibleViews.length) {
        this.__collapsibleViews[idx].setCollapsed(false);
      }
    }
  }
});
